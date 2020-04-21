import os
from gettext import gettext as _
import logging
import shutil

import createrepo_c as cr
import libcomps

from django.core.files import File

from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    ContentArtifact,
    RepositoryVersion,
    PublishedArtifact,
    PublishedMetadata,
)

from pulpcore.plugin.tasking import WorkingDirectory

from pulp_rpm.app.comps import dict_to_strdict
from pulp_rpm.app.constants import CHECKSUM_TYPES, PACKAGES_DIRECTORY
from pulp_rpm.app.models import (
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RepoMetadataFile,
    RpmPublication,
    UpdateRecord,
)

log = logging.getLogger(__name__)

REPODATA_PATH = 'repodata'


class PublicationData:
    """
    Encapsulates data relative to publication.

    Attributes:
        publication (pulpcore.plugin.models.Publication): A Publication to populate.
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
        self.sub_repos = []
        self.repomdrecords = []

    def prepare_metadata_files(self, content, folder=None):
        """
        Copies metadata files from the Artifact storage.

        Args:
            content (pulpcore.plugin.models.Content): content set.

        Keyword Args:
            folder(str): name of the directory.

        Returns:
            repomdrecords (list): A list of tuples with repomdrecords data.

        """
        repomdrecords = []
        repo_metadata_files = RepoMetadataFile.objects.filter(
            pk__in=content).prefetch_related('contentartifact_set')

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

    def publish_artifacts(self, content):
        """
        Publish artifacts.

        Args:
            content (pulpcore.plugin.models.Content): content set.

        """
        published_artifacts = []
        for content_artifact in ContentArtifact.objects.filter(
                content__in=content.exclude(
                    pulp_type__in=[RepoMetadataFile.get_pulp_type(),
                                   Modulemd.get_pulp_type(),
                                   ModulemdDefaults.get_pulp_type()]
                ).distinct()
        ).iterator():
            relative_path = content_artifact.relative_path
            if content_artifact.content.pulp_type == Package.get_pulp_type():
                relative_path = os.path.join(
                    PACKAGES_DIRECTORY,
                    relative_path.lower()[0],
                    content_artifact.relative_path
                )
            published_artifacts.append(PublishedArtifact(
                relative_path=relative_path,
                publication=self.publication,
                content_artifact=content_artifact)
            )

        PublishedArtifact.objects.bulk_create(published_artifacts, batch_size=2000)

    def handle_sub_repos(self, distribution_tree):
        """
        Get sub-repo content and publish them.

        Args:
            distribution_tree (pulp_rpm.models.DistributionTree): A distribution_tree object.

        """
        relations = ["addon", "variant"]
        for relation in relations:
            addons_or_variants = getattr(distribution_tree, f"{relation}s").all()
            for addon_or_variant in addons_or_variants:
                repository = addon_or_variant.repository.cast()
                repository_version = repository.latest_version()

                if repository_version and repository.sub_repo:
                    addon_or_variant_id = getattr(addon_or_variant, f"{relation}_id")
                    self.sub_repos.append((
                        addon_or_variant_id,
                        repository_version.content,
                        repository.original_checksum_types
                    ))

    def populate(self):
        """
        Populate a publication.

        Create published artifacts for a publication.

        """
        main_content = self.publication.repository_version.content
        self.repomdrecords = self.prepare_metadata_files(main_content)

        distribution_trees = DistributionTree.objects.filter(
            pk__in=main_content
        ).prefetch_related(
            "addons",
            "variants",
            "addons__repository",
            "variants__repository",
            "contentartifact_set"
        )

        for distribution_tree in distribution_trees:
            self.handle_sub_repos(distribution_tree)

        all_content = main_content
        for name, content, checksum_types in self.sub_repos:
            os.mkdir(name)
            setattr(self, f"{name}_content", content)
            setattr(self, f"{name}_checksums", checksum_types)
            setattr(self, f"{name}_repomdrecords", self.prepare_metadata_files(content, name))
            all_content |= content
        self.publish_artifacts(all_content)


def get_checksum_type(name, checksum_types):
    """
    Get checksum algorithm for publishing metadata.

    Args:
        name (str): Name of the metadata type.
        checksum_types (dict): Checksum types for metadata and packages.

    """
    original = checksum_types.get("original")
    metadata = checksum_types.get("metadata")
    checksum_type = original.get(name, CHECKSUM_TYPES.SHA256)

    if metadata:
        checksum_type = metadata

    return getattr(cr, checksum_type.upper(), cr.SHA256)


def publish(repository_version_pk, metadata_signing_service=None, checksum_types=None):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a publication from this repository version.
        metadata_signing_service (pulpcore.app.models.AsciiArmoredDetachedSigningService):
            A reference to an associated signing service.
        checksum_types (dict): Checksum types for metadata and packages.

    """
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)
    repository = repository_version.repository.cast()
    checksum_types = checksum_types or {}
    checksum_types["original"] = repository.original_checksum_types
    original_metadata_checksum_type = repository.original_checksum_types.get(
        "primary", CHECKSUM_TYPES.SHA256)

    log.info(_('Publishing: repository={repo}, version={version}').format(
        repo=repository.name,
        version=repository_version.number,
    ))

    with WorkingDirectory():
        with RpmPublication.create(repository_version) as publication:
            publication.package_checksum_type = checksum_types.get(
                "package", CHECKSUM_TYPES.SHA256)
            publication.metadata_checksum_type = checksum_types.get(
                "metadata", original_metadata_checksum_type)
            publication_data = PublicationData(publication)
            publication_data.populate()

            content = publication.repository_version.content

            # Main repo
            create_repomd_xml(
                content, publication, checksum_types, publication_data.repomdrecords,
                metadata_signing_service=metadata_signing_service
            )

            for sub_repo in publication_data.sub_repos:
                name = sub_repo[0]
                checksum_types["original"] = getattr(publication_data, f"{name}_checksums")
                content = getattr(publication_data, f"{name}_content")
                extra_repomdrecords = getattr(publication_data, f"{name}_repomdrecords")
                create_repomd_xml(
                    content, publication, checksum_types, extra_repomdrecords, name,
                    metadata_signing_service=metadata_signing_service
                )


def create_repomd_xml(content, publication, checksum_types, extra_repomdrecords,
                      sub_folder=None, metadata_signing_service=None):
    """
    Creates a repomd.xml file.

    Args:
        content(app.models.Content): content set
        publication(pulpcore.plugin.models.Publication): the publication
        extra_repomdrecords(list): list with data relative to repo metadata files
        sub_folder(str): name of the folder for sub repos
        metadata_signing_service (pulpcore.app.models.AsciiArmoredDetachedSigningService):
            A reference to an associated signing service.

    """
    cwd = os.getcwd()
    repodata_path = REPODATA_PATH
    has_modules = False
    has_comps = False
    package_checksum_type = checksum_types.get("package")

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
    comps_xml_path = os.path.join(cwd, "comps.xml")

    pri_xml = cr.PrimaryXmlFile(pri_xml_path)
    fil_xml = cr.FilelistsXmlFile(fil_xml_path)
    oth_xml = cr.OtherXmlFile(oth_xml_path)
    pri_db = cr.PrimarySqlite(pri_db_path)
    fil_db = cr.FilelistsSqlite(fil_db_path)
    oth_db = cr.OtherSqlite(oth_db_path)
    upd_xml = cr.UpdateInfoXmlFile(upd_xml_path)

    packages = Package.objects.filter(pk__in=content)
    total_packages = packages.count()

    pri_xml.set_num_of_pkgs(total_packages)
    fil_xml.set_num_of_pkgs(total_packages)
    oth_xml.set_num_of_pkgs(total_packages)

    # Process all packages
    for package in packages.iterator():
        pkg = package.to_createrepo_c(package_checksum_type)
        pkg_filename = os.path.basename(package.location_href)
        # this can cause an issue when two same RPM package names appears
        # a/name1.rpm b/name1.rpm
        pkg.location_href = os.path.join(
            PACKAGES_DIRECTORY,
            pkg_filename[0].lower(),
            pkg_filename
        )
        pri_xml.add_pkg(pkg)
        fil_xml.add_pkg(pkg)
        oth_xml.add_pkg(pkg)
        pri_db.add_pkg(pkg)
        fil_db.add_pkg(pkg)
        oth_db.add_pkg(pkg)

    # Process update records
    for update_record in UpdateRecord.objects.filter(pk__in=content).iterator():
        upd_xml.add_chunk(cr.xml_dump_updaterecord(update_record.to_createrepo_c()))

    # Process modulemd and modulemd_defaults
    with open(mod_yml_path, 'ab') as mod_yml:
        for modulemd in Modulemd.objects.filter(pk__in=content).iterator():
            mod_yml.write(modulemd._artifacts.get().file.read())
            has_modules = True
        for default in ModulemdDefaults.objects.filter(pk__in=content).iterator():
            mod_yml.write(default._artifacts.get().file.read())
            has_modules = True

    # Process comps
    comps = libcomps.Comps()
    for pkg_grp in PackageGroup.objects.filter(pk__in=content).iterator():
        group = pkg_grp.pkg_grp_to_libcomps()
        comps.groups.append(group)
        has_comps = True
    for pkg_cat in PackageCategory.objects.filter(pk__in=content).iterator():
        cat = pkg_cat.pkg_cat_to_libcomps()
        comps.categories.append(cat)
        has_comps = True
    for pkg_env in PackageEnvironment.objects.filter(pk__in=content).iterator():
        env = pkg_env.pkg_env_to_libcomps()
        comps.environments.append(env)
        has_comps = True
    for pkg_lng in PackageLangpacks.objects.filter(pk__in=content).iterator():
        comps.langpacks = dict_to_strdict(pkg_lng.matches)
        has_comps = True

    comps.toxml_f(comps_xml_path, xml_options={"default_explicit": True,
                                               "empty_groups": True,
                                               "uservisible_explicit": True})

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

    if has_comps:
        repomdrecords.append(("group", comps_xml_path, None))

    repomdrecords.extend(extra_repomdrecords)

    sqlite_files = ("primary_db", "filelists_db", "other_db")
    for name, path, db_to_update in repomdrecords:
        record = cr.RepomdRecord(name, path)
        checksum_type = get_checksum_type(name, checksum_types)
        if name in sqlite_files:
            record_bz = record.compress_and_fill(checksum_type, cr.BZ2)
            record_bz.type = name
            record_bz.rename_file()
            path = record_bz.location_href.split('/')[-1]
            repomd.set_record(record_bz)
        else:
            record.fill(checksum_type)
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

    if metadata_signing_service:
        signing_service = AsciiArmoredDetachedSigningService.objects.get(
            pk=metadata_signing_service.pk
        )
        sign_results = signing_service.sign(repomd_path)

        # publish a signed file
        PublishedMetadata.create_from_file(
            relative_path=os.path.join(repodata_path, os.path.basename(sign_results['file'])),
            publication=publication,
            file=File(open(sign_results['file'], 'rb'))
        )

        # publish a detached signature
        PublishedMetadata.create_from_file(
            relative_path=os.path.join(repodata_path, os.path.basename(sign_results['signature'])),
            publication=publication,
            file=File(open(sign_results['signature'], 'rb'))
        )

        # publish a public key required for further verification
        PublishedMetadata.create_from_file(
            relative_path=os.path.join(repodata_path, os.path.basename(sign_results['key'])),
            publication=publication,
            file=File(open(sign_results['key'], 'rb'))
        )
    else:
        PublishedMetadata.create_from_file(
            relative_path=os.path.join(repodata_path, os.path.basename(repomd_path)),
            publication=publication,
            file=File(open(repomd_path, 'rb'))
        )
