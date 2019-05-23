import os
from gettext import gettext as _
import logging

import createrepo_c as cr

from django.core.files import File
from django.utils.dateparse import parse_datetime

from pulpcore.plugin.models import RepositoryVersion, PublishedArtifact, PublishedMetadata

from pulpcore.plugin.tasking import WorkingDirectory

from pulp_rpm.app.models import Package, RpmPublication, UpdateRecord

log = logging.getLogger(__name__)

REPODATA_PATH = "repodata"


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


def publish(repository_version_pk):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a publication from this repository version.
    """
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(
        _("Publishing: repository={repo}, version={version}").format(
            repo=repository_version.repository.name, version=repository_version.number
        )
    )

    with WorkingDirectory():
        with RpmPublication.create(repository_version) as publication:
            packages = populate(publication)

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

            pri_xml.set_num_of_pkgs(len(packages))
            fil_xml.set_num_of_pkgs(len(packages))
            oth_xml.set_num_of_pkgs(len(packages))

            # Process all packages
            for package in packages:
                pkg = package.to_createrepo_c()
                pkg.location_href = package.contentartifact_set.first().relative_path
                pri_xml.add_pkg(pkg)
                fil_xml.add_pkg(pkg)
                oth_xml.add_pkg(pkg)
                pri_db.add_pkg(pkg)
                fil_db.add_pkg(pkg)
                oth_db.add_pkg(pkg)

            # Process update records
            for update_record in UpdateRecord.objects.filter(
                pk__in=publication.repository_version.content
            ):
                upd_xml.add_chunk(update_record_xml(update_record))

            pri_xml.close()
            fil_xml.close()
            oth_xml.close()
            upd_xml.close()

            repomd = cr.Repomd()

            repomdrecords = (
                ("primary", pri_xml_path, pri_db),
                ("filelists", fil_xml_path, fil_db),
                ("other", oth_xml_path, oth_db),
                ("primary_db", pri_db_path, None),
                ("filelists_db", fil_db_path, None),
                ("other_db", oth_db_path, None),
                ("updateinfo", upd_xml_path, None),
            )

            sqlite_files = ("primary_db", "filelists_db", "other_db")
            for name, path, db_to_update in repomdrecords:
                record = cr.RepomdRecord(name, path)
                if name in sqlite_files:
                    record_bz = record.compress_and_fill(cr.SHA256, cr.BZ2)
                    record_bz.type = name
                    record_bz.rename_file()
                    path = record_bz.location_href.split("/")[-1]
                    repomd.set_record(record_bz)
                else:
                    record.fill(cr.SHA256)
                    if db_to_update:
                        db_to_update.dbinfo_update(record.checksum)
                        db_to_update.close()
                    record.rename_file()
                    path = record.location_href.split("/")[-1]
                    repomd.set_record(record)
                metadata = PublishedMetadata(
                    relative_path=os.path.join(REPODATA_PATH, os.path.basename(path)),
                    publication=publication,
                    file=File(open(os.path.basename(path), "rb")),
                )
                metadata.save()

            with open(repomd_path, "w") as repomd_f:
                repomd_f.write(repomd.xml_dump())

            metadata = PublishedMetadata(
                relative_path=os.path.join(REPODATA_PATH, os.path.basename(repomd_path)),
                publication=publication,
                file=File(open(os.path.basename(repomd_path), "rb")),
            )
            metadata.save()


def populate(publication):
    """
    Populate a publication.

    Create published artifacts for a publication.

    Args:
        publication (pulpcore.plugin.models.Publication): A Publication to populate.

    Returns:
        packages (pulp_rpm.models.Package): A list of published packages.

    """
    packages = Package.objects.filter(
        pk__in=publication.repository_version.content
    ).prefetch_related("contentartifact_set")
    published_artifacts = []

    for package in packages:
        for content_artifact in package.contentartifact_set.all():
            published_artifacts.append(
                PublishedArtifact(
                    relative_path=content_artifact.relative_path,
                    publication=publication,
                    content_artifact=content_artifact,
                )
            )

    PublishedArtifact.objects.bulk_create(published_artifacts)

    return packages
