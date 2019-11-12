import os
from gettext import gettext as _
import logging
import shutil

import createrepo_c as cr

from django.core.files import File
from django.utils.dateparse import parse_datetime

from pulpcore.plugin.models import (
    RepositoryVersion,
    PublishedArtifact,
    PublishedMetadata,
)

from pulpcore.plugin.tasking import WorkingDirectory

from pulp_rpm.app.models import (
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    Package,
    RepoMetadataFile,
    RpmPublication,
    UpdateRecord,
)
from pulp_rpm.app.tasks.utils import create_treeinfo

log = logging.getLogger(__name__)

REPODATA_PATH = 'repodata'


class PublicationData:
    """
    Encapsulates data relative to publication.

    Attributes:
        publication (pulpcore.plugin.models.Publication): A Publication to populate.
        packages (pulp_rpm.models.Package): A list of published packages.
        published_artifacts (pulpcore.plugin.models.PublishedArtifact): A published artifacts list.
        sub_repos (list): A list of tuples with sub_repos data.
        repomdrecords (list): A list of tuples with repomdrecords data.

    """

    def __init__(self, publication):
        """
        Setting Publication data.

        Args:
            publication (pulpcore.plugin.models.Publication): A Publication to populate.

        """
        self.publication = publication
        self.packages = []
        self.published_artifacts = []
        self.sub_repos = []
        self.repomdrecords = []

    def prepare_metadata_files(self, contents, folder=None):
        """
        Copies metadata files from the Artifact storage.

        Args:
            contents (pulpcore.plugin.models.Content): A list of contents.

        Keyword Args:
            folder(str): name of the directory.

        Returns:
            repomdrecords (list): A list of tuples with repomdrecords data.

        """
        repomdrecords = []
        repo_metadata_files = RepoMetadataFile.objects.filter(
            pk__in=contents).prefetch_related('contentartifact_set')

        for repo_metadata_file in repo_metadata_files:
            content_artifact = repo_metadata_file.contentartifact_set.get()
            current_file = content_artifact.artifact.file.file
            path = content_artifact.relative_path.split("/")[-1]
            if repo_metadata_file.checksum in path:
                path = path.split("-")[-1]
            if folder:
                path = os.path.join(folder, path)
            with open(path, "wb") as new_file:
                shutil.copyfileobj(current_file, new_file)
                repomdrecords.append((repo_metadata_file.data_type, new_file.name, None))

        return repomdrecords

    def get_packages(self, contents):
        """
        Get packages from content.

        Args:
            contents (pulpcore.plugin.models.Content): A list of contents.

        Returns:
            packages (pulp_rpm.models.Package): A list of packages.

        """
        packages = Package.objects.filter(pk__in=contents).\
            prefetch_related('contentartifact_set')

        return packages

    def populate(self):
        """
        Populate a publication.

        Create published artifacts for a publication.

        """
        publication = self.publication
        main_content = publication.repository_version.content

        distribution_trees = DistributionTree.objects.filter(
            pk__in=publication.repository_version.content
        ).prefetch_related(
            "addons",
            "variants",
            "addons__repository",
            "variants__repository",
            "contentartifact_set"
        )

        for distribution_tree in distribution_trees:
            for content_artifact in distribution_tree.contentartifact_set.all():
                self.published_artifacts.append(PublishedArtifact(
                    relative_path=content_artifact.relative_path,
                    publication=publication,
                    content_artifact=content_artifact)
                )
            for addon in distribution_tree.addons.all():
                repository_version = RepositoryVersion.latest(addon.repository)
                if repository_version and repository_version.content != main_content:
                    self.sub_repos.append((addon.addon_id, repository_version.content))
            for variant in distribution_tree.variants.all():
                repository_version = RepositoryVersion.latest(variant.repository)
                if repository_version and repository_version.content != main_content:
                    self.sub_repos.append((variant.variant_id, repository_version.content))

            treeinfo_file = create_treeinfo(distribution_tree)
            PublishedMetadata.create_from_file(
                publication=publication,
                file=File(open(treeinfo_file.name, 'rb'))
            )

        self.packages = self.get_packages(main_content)
        self.repomdrecords = self.prepare_metadata_files(main_content)

        all_packages = self.packages
        for name, content in self.sub_repos:
            os.mkdir(name)
            sub_repo_packages = self.get_packages(content)
            all_packages = all_packages | sub_repo_packages
            setattr(self, f"{name}_packages", sub_repo_packages)
            setattr(self, f"{name}_repomdrecords", self.prepare_metadata_files(content, name))

        for package in all_packages.distinct():
            for content_artifact in package.contentartifact_set.all():
                self.published_artifacts.append(PublishedArtifact(
                    relative_path=content_artifact.relative_path,
                    publication=self.publication,
                    content_artifact=content_artifact)
                )

        PublishedArtifact.objects.bulk_create(self.published_artifacts)


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

    log.info(_('Publishing: repository={repo}, version={version}').format(
        repo=repository_version.repository.name,
        version=repository_version.number,
    ))

    with WorkingDirectory():
        with RpmPublication.create(repository_version) as publication:
            publication_data = PublicationData(publication)
            publication_data.populate()

            packages = publication_data.packages

            # Main repo
            create_rempomd_xml(packages, publication, publication_data.repomdrecords)

            for sub_repo in publication_data.sub_repos:
                name = sub_repo[0]
                packages = getattr(publication_data, f"{name}_packages")
                extra_repomdrecords = getattr(publication_data, f"{name}_repomdrecords")
                create_rempomd_xml(packages, publication, extra_repomdrecords, name)


def create_rempomd_xml(packages, publication, extra_repomdrecords, sub_folder=None):
    """
    Creates a repomd.xml file.

    Args:
        packages(app.models.Package): set of packages
        publication(pulpcore.plugin.models.Publication): the publication
        extra_repomdrecords(list): list with data relative to repo metadata files
        sub_folder(str): name of the folder for sub repos

    """
    cwd = os.getcwd()
    repodata_path = REPODATA_PATH
    has_modules = False

    if sub_folder:
        cwd = os.path.join(cwd, sub_folder)
        repodata_path = os.path.join(sub_folder, repodata_path)

    # Prepare metadata files
    repomd_path = os.path.join(cwd, "repomd.xml")
    pri_xml_path = os.path.join(cwd, "primary.xml.gz")
    fil_xml_path = os.path.join(cwd, "filelists.xml.gz")
    oth_xml_path = os.path.join(cwd, "other.xml.gz")
    pri_db_path = os.path.join(cwd, "primary.sqlite")
    fil_db_path = os.path.join(cwd, "filelists.sqlite")
    oth_db_path = os.path.join(cwd, "other.sqlite")
    upd_xml_path = os.path.join(cwd, "updateinfo.xml.gz")
    mod_yml_path = os.path.join(cwd, "modules.yaml")

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
            pk__in=publication.repository_version.content):
        upd_xml.add_chunk(update_record_xml(update_record))

    # Process modulemd and modulemd_defaults
    with open(mod_yml_path, 'ab') as mod_yml:
        for modulemd in Modulemd.objects.filter(
                pk__in=publication.repository_version.content):
            mod_yml.write(modulemd._artifacts.get().file.read())
            has_modules = True
        for default in ModulemdDefaults.objects.filter(
                pk__in=publication.repository_version.content):
            mod_yml.write(default._artifacts.get().file.read())
            has_modules = True

    pri_xml.close()
    fil_xml.close()
    oth_xml.close()
    upd_xml.close()

    repomd = cr.Repomd()

    repomdrecords = [("primary", pri_xml_path, pri_db),
                     ("filelists", fil_xml_path, fil_db),
                     ("other", oth_xml_path, oth_db),
                     ("primary_db", pri_db_path, None),
                     ("filelists_db", fil_db_path, None),
                     ("other_db", oth_db_path, None),
                     ("updateinfo", upd_xml_path, None)]

    if has_modules:
        repomdrecords.append(("modules", mod_yml_path, None))

    repomdrecords.extend(extra_repomdrecords)

    sqlite_files = ("primary_db", "filelists_db", "other_db")
    for name, path, db_to_update in repomdrecords:
        record = cr.RepomdRecord(name, path)
        if name in sqlite_files:
            record_bz = record.compress_and_fill(cr.SHA256, cr.BZ2)
            record_bz.type = name
            record_bz.rename_file()
            path = record_bz.location_href.split('/')[-1]
            repomd.set_record(record_bz)
        elif name == "modules":
            record_md = record.compress_and_fill(cr.SHA256, cr.GZ)
            record_md.type = name
            record_md.rename_file()
            path = record_md.location_href.split('/')[-1]
            repomd.set_record(record_md)
        else:
            record.fill(cr.SHA256)
            if (db_to_update):
                db_to_update.dbinfo_update(record.checksum)
                db_to_update.close()
            record.rename_file()
            path = record.location_href.split('/')[-1]
            repomd.set_record(record)

        if sub_folder:
            path = os.path.join(sub_folder, path)

        PublishedMetadata.create_from_file(
            relative_path=os.path.join(repodata_path, os.path.basename(path)),
            publication=publication,
            file=File(open(path, 'rb'))
        )

    with open(repomd_path, "w") as repomd_f:
        repomd_f.write(repomd.xml_dump())

    PublishedMetadata.create_from_file(
        relative_path=os.path.join(repodata_path, os.path.basename(repomd_path)),
        publication=publication,
        file=File(open(repomd_path, 'rb'))
    )
