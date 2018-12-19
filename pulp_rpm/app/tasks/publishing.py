import os
from gettext import gettext as _
import logging

import createrepo_c as cr

from django.core.files import File
from django.utils.dateparse import parse_datetime

from pulpcore.plugin.models import (
    RepositoryVersion,
    Publication,
    PublishedArtifact,
    PublishedMetadata,
    RemoteArtifact,
)

from pulpcore.plugin.tasking import WorkingDirectory

from pulp_rpm.app.models import Package, RpmPublisher, UpdateRecord

log = logging.getLogger(__name__)

REPODATA_PATH = 'repodata'


def update_record_xml(update_record):
    """
    Return xml for an UpdateRecord.

    Args:
        update_record (app.models.UpdateRecord): create xml from this record

    Returns:
        str: xml for the UpdateRecord

    """
    rec = cr.UpdateRecord()
    rec.fromstr = update_record.fromstr
    rec.status = update_record.status
    rec.type = update_record.type
    rec.version = update_record.version
    rec.id = update_record.id
    rec.title = update_record.title
    rec.issued_date = parse_datetime(update_record.issued_date)
    rec.updated_date = parse_datetime(update_record.updated_date)
    rec.rights = update_record.rights
    rec.summary = update_record.summary
    rec.description = update_record.description

    for collection in update_record.collections.all():
        col = cr.UpdateCollection()
        col.shortname = collection.shortname
        col.name = collection.name

        for package in collection.packages.all():
            pkg = cr.UpdateCollectionPackage()
            pkg.name = package.name
            pkg.version = package.version
            pkg.release = package.release
            pkg.epoch = package.epoch
            pkg.arch = package.arch
            pkg.src = package.src
            pkg.filename = package.filename
            pkg.reboot_suggested = package.reboot_suggested
            if package.sum:
                pkg.sum = package.sum
                pkg.sum_type = int(package.sum_type or 0)
            col.append(pkg)

        rec.append_collection(col)

    for reference in update_record.references.all():
        ref = cr.UpdateReference()
        ref.href = reference.href
        ref.id = reference.ref_id
        ref.type = reference.ref_type
        ref.title = reference.title

        rec.append_reference(ref)

    return cr.xml_dump_updaterecord(rec)


def publish(publisher_pk, repository_version_pk):
    """
    Use provided publisher to create a Publication based on a RepositoryVersion.

    Args:
        publisher_pk (str): Use the publish settings provided by this publisher.
        repository_version_pk (str): Create a publication from this repository version.
    """
    publisher = RpmPublisher.objects.get(pk=publisher_pk)
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(_('Publishing: repository={repo}, version={version}, publisher={publisher}').format(
        repo=repository_version.repository.name,
        version=repository_version.number,
        publisher=publisher.name,
    ))

    with WorkingDirectory():
        with Publication.create(repository_version, publisher) as publication:
            populate(publication)

            # Prepare metadata files
            repomd_path = os.path.join(os.getcwd(), "repomd.xml")
            pri_xml_path = os.path.join(os.getcwd(), "primary.xml.gz")
            fil_xml_path = os.path.join(os.getcwd(), "filelists.xml.gz")
            oth_xml_path = os.path.join(os.getcwd(), "other.xml.gz")
            pri_db_path = os.path.join(os.getcwd(), "primary.sqlite")
            fil_db_path = os.path.join(os.getcwd(), "filelists.sqlite")
            oth_db_path = os.path.join(os.getcwd(), "other.sqlite")
            upd_xml_path = os.path.join(os.getcwd(), "updateinfo.xml.gz")

            pri_xml = cr.PrimaryXmlFile(pri_xml_path)
            fil_xml = cr.FilelistsXmlFile(fil_xml_path)
            oth_xml = cr.OtherXmlFile(oth_xml_path)
            pri_db = cr.PrimarySqlite(pri_db_path)
            fil_db = cr.FilelistsSqlite(fil_db_path)
            oth_db = cr.OtherSqlite(oth_db_path)
            upd_xml = cr.UpdateInfoXmlFile(upd_xml_path)

            artifacts = publication.published_artifact.all()
            pri_xml.set_num_of_pkgs(len(artifacts))
            fil_xml.set_num_of_pkgs(len(artifacts))
            oth_xml.set_num_of_pkgs(len(artifacts))

            # Process all packages
            for artifact in artifacts:
                # TODO: pass attributes from db rather than use the filesystem
                pkg = cr.package_from_rpm(artifact.content_artifact.artifact.file.path)
                pkg.location_href = artifact.content_artifact.relative_path
                pri_xml.add_pkg(pkg)
                fil_xml.add_pkg(pkg)
                oth_xml.add_pkg(pkg)
                pri_db.add_pkg(pkg)
                fil_db.add_pkg(pkg)
                oth_db.add_pkg(pkg)

            # Process update records
            for update_record in UpdateRecord.objects.filter(
                    pk__in=publication.repository_version.content):
                upd_xml.add_chunk(update_record_xml(update_record))

            pri_xml.close()
            fil_xml.close()
            oth_xml.close()
            upd_xml.close()

            repomd = cr.Repomd()

            repomdrecords = (("primary", pri_xml_path, pri_db),
                             ("filelists", fil_xml_path, fil_db),
                             ("other", oth_xml_path, oth_db),
                             ("primary_db", pri_db_path, None),
                             ("filelists_db", fil_db_path, None),
                             ("other_db", oth_db_path, None),
                             ("updateinfo", upd_xml_path, None))

            for name, path, db_to_update in repomdrecords:
                record = cr.RepomdRecord(name, path)
                record.fill(cr.SHA256)
                if (db_to_update):
                    db_to_update.dbinfo_update(record.checksum)
                    db_to_update.close()
                repomd.set_record(record)
                metadata = PublishedMetadata(
                    relative_path=os.path.join(REPODATA_PATH, os.path.basename(path)),
                    publication=publication,
                    file=File(open(os.path.basename(path), 'rb'))
                )
                metadata.save()

            open(repomd_path, "w").write(repomd.xml_dump())

            metadata = PublishedMetadata(
                relative_path=os.path.join(REPODATA_PATH, os.path.basename(repomd_path)),
                publication=publication,
                file=File(open(os.path.basename(repomd_path), 'rb'))
            )
            metadata.save()


def populate(publication):
    """
    Populate a publication.

    Create published artifacts for a publication.

    Args:
        publication (pulpcore.plugin.models.Publication): A Publication to populate.

    """
    def find_artifact():
        _artifact = content_artifact.artifact
        if not _artifact:
            _artifact = RemoteArtifact.objects.filter(content_artifact=content_artifact).first()
        return _artifact

    for package in Package.objects.filter(pk__in=publication.repository_version.content):
        for content_artifact in package.contentartifact_set.all():
            published_artifact = PublishedArtifact(
                relative_path=content_artifact.relative_path,
                publication=publication,
                content_artifact=content_artifact)
            published_artifact.save()
