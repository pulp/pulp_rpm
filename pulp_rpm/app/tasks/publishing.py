from collections import defaultdict
from gettext import gettext as _
import os
import logging
import shutil
import tempfile

import createrepo_c as cr
import libcomps

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage as storage
from django.db.models import Q

from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    ContentArtifact,
    RepositoryVersion,
    ProgressReport,
    PublishedArtifact,
    PublishedMetadata,
)

from pulp_rpm.app.comps import dict_to_strdict
from pulp_rpm.app.constants import ALLOWED_CHECKSUM_ERROR_MSG, CHECKSUM_TYPES, PACKAGES_DIRECTORY
from pulp_rpm.app.kickstart.treeinfo import PulpTreeInfo, TreeinfoData
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

REPODATA_PATH = "repodata"


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
        repo_metadata_files = RepoMetadataFile.objects.filter(pk__in=content).prefetch_related(
            "contentartifact_set"
        )

        for repo_metadata_file in repo_metadata_files:
            if repo_metadata_file.unsupported_metadata_type:
                # Normally these types are not synced in the first place, we skip them here, since
                # they might still exist in old repo versions from before we started excluding them.
                continue
            content_artifact = repo_metadata_file.contentartifact_set.get()
            current_file = content_artifact.artifact.file.file
            path = content_artifact.relative_path.split("/")[-1]
            if repo_metadata_file.checksum in path:
                # filenames can be checksum-xxxx.yyy - but can also be checksum-mmm-nnn-ooo.yyy
                # Some old repos might have filename of checksum only so we need to take care
                # of that too
                # split off the checksum, keep the rest
                filename = path.split("-")[1:]
                if filename:
                    path = "-".join(filename)
            if folder:
                path = os.path.join(folder, path)
            with open(path, "wb") as new_file:
                shutil.copyfileobj(current_file, new_file)
                repomdrecords.append((repo_metadata_file.data_type, new_file.name, None))

        return repomdrecords

    def publish_artifacts(self, content, prefix=""):
        """
        Publish artifacts.

        Args:
            content (pulpcore.plugin.models.Content): content set.
            prefix (str): a relative path prefix for the published artifact

        """
        published_artifacts = []

        # Special case for Packages
        contentartifact_qs = (
            ContentArtifact.objects.filter(content__in=content)
            .filter(content__pulp_type=Package.get_pulp_type())
            .select_related("content__rpm_package__time_build")
        )

        rel_path_mapping = defaultdict(list)
        # Some Suboptimal Repos have the 'same' artifact living in multiple places.
        # Specifically, the same NEVRA, in more than once place, **with different checksums**
        # (since if all that was different was location_href there would be only one
        # ContentArtifact in the first place).
        #
        # pulp_rpm wants to publish a 'canonical' repository-layout, under which an RPM
        # "name-version-release-arch" appears at "Packages/n/name-version-release-arch.rpm".
        # Because the assumption is that Packages don't "own" their path, only the filename
        # is kept as relative_path.
        #
        # In this case, we have to pick one - which is essentially what the rest of the RPM
        # Ecosystem does when faced with the impossible. This code takes the one with the
        # most recent build time which is the same heuristic used by Yum/DNF/Zypper.
        #
        # Note that this only impacts user-created publications, which produce the "standard"
        # RPM layout of repo/Packages/f/foo.rpm. A publication created by mirror-sync retains
        # whatever layout their "upstream" repo-metadata dictates.
        fields = ["pk", "relative_path", "content__rpm_package__time_build"]
        for content_artifact in contentartifact_qs.values(*fields).iterator():
            relative_path = content_artifact["relative_path"]
            time_build = content_artifact["content__rpm_package__time_build"]

            relative_path = os.path.join(
                prefix, PACKAGES_DIRECTORY, relative_path.lower()[0], relative_path
            )
            rel_path_mapping[relative_path].append((content_artifact["pk"], time_build))

        for rel_path, content_artifacts in rel_path_mapping.items():
            # sort the content artifacts by when the package was built
            if len(content_artifacts) > 1:
                content_artifacts.sort(key=lambda p: p[1], reverse=True)
                log.warning(
                    "Duplicate packages found competing for {path}, selected the one with "
                    "the most recent build time, excluding {others} others.".format(
                        path=rel_path, others=len(content_artifacts[1:])
                    )
                )

            # Only add the first one (the one with the highest build time)
            published_artifacts.append(
                PublishedArtifact(
                    relative_path=rel_path,
                    publication=self.publication,
                    content_artifact_id=content_artifacts[0][0],
                )
            )

        # Handle everything else
        is_treeinfo = Q(relative_path__in=["treeinfo", ".treeinfo"])
        unpublishable_types = Q(
            content__pulp_type__in=[
                RepoMetadataFile.get_pulp_type(),
                Modulemd.get_pulp_type(),
                ModulemdDefaults.get_pulp_type(),
                # already dealt with
                Package.get_pulp_type(),
            ]
        )

        contentartifact_qs = (
            ContentArtifact.objects.filter(content__in=content)
            .exclude(unpublishable_types)
            .exclude(is_treeinfo)
        )

        for content_artifact in contentartifact_qs.values("pk", "relative_path").iterator():
            published_artifacts.append(
                PublishedArtifact(
                    relative_path=content_artifact["relative_path"],
                    publication=self.publication,
                    content_artifact_id=content_artifact["pk"],
                )
            )

        PublishedArtifact.objects.bulk_create(published_artifacts, batch_size=2000)

    def handle_sub_repos(self, distribution_tree):
        """
        Get sub-repo content and publish them.

        Args:
            distribution_tree (pulp_rpm.models.DistributionTree): A distribution_tree object.

        """
        original_treeinfo_content_artifact = distribution_tree.contentartifact_set.get(
            relative_path__in=[".treeinfo", "treeinfo"]
        )
        artifact_file = storage.open(original_treeinfo_content_artifact.artifact.file.name)
        with tempfile.NamedTemporaryFile("wb", dir=".") as temp_file:
            shutil.copyfileobj(artifact_file, temp_file)
            temp_file.flush()
            treeinfo = PulpTreeInfo()
            treeinfo.load(f=temp_file.name)
            treeinfo_data = TreeinfoData(treeinfo.parsed_sections())

            # rewrite the treeinfo file such that the variant repository and package location
            # is a relative subtree
            treeinfo.rewrite_subrepo_paths(treeinfo_data)

            # TODO: better way to do this?
            main_variant = treeinfo.original_parser._sections.get("general", {}).get(
                "variant", None
            )
            treeinfo_file = tempfile.NamedTemporaryFile(dir=".")
            treeinfo.dump(treeinfo_file.name, main_variant=main_variant)
            with open(treeinfo_file.name, "rb") as treeinfo_fd:
                PublishedMetadata.create_from_file(
                    relative_path=original_treeinfo_content_artifact.relative_path,
                    publication=self.publication,
                    file=File(treeinfo_fd),
                )
        artifact_file.close()
        relations = ["addon", "variant"]
        for relation in relations:
            addons_or_variants = getattr(distribution_tree, f"{relation}s").all()
            for addon_or_variant in addons_or_variants:
                if not addon_or_variant.repository:
                    # a variant of the main repo
                    continue
                repository = addon_or_variant.repository.cast()
                repository_version = repository.latest_version()

                if repository_version and repository.user_hidden:
                    addon_or_variant_id = getattr(addon_or_variant, f"{relation}_id")
                    self.sub_repos.append(
                        (
                            addon_or_variant_id,
                            repository_version.content,
                            repository.original_checksum_types,
                        )
                    )

    def populate(self):
        """
        Populate a publication.

        Create published artifacts for a publication.

        """
        main_content = self.publication.repository_version.content
        self.repomdrecords = self.prepare_metadata_files(main_content)

        self.publish_artifacts(main_content)

        distribution_trees = DistributionTree.objects.filter(pk__in=main_content).prefetch_related(
            "addons",
            "variants",
            "addons__repository",
            "variants__repository",
            "contentartifact_set",
        )

        for distribution_tree in distribution_trees:
            self.handle_sub_repos(distribution_tree)

        for name, content, checksum_types in self.sub_repos:
            os.mkdir(name)
            setattr(self, f"{name}_content", content)
            setattr(self, f"{name}_checksums", checksum_types)
            setattr(self, f"{name}_repomdrecords", self.prepare_metadata_files(content, name))
            self.publish_artifacts(content, prefix=name)


def get_checksum_type(name, checksum_types, default=CHECKSUM_TYPES.SHA256):
    """
    Get checksum algorithm for publishing metadata.

    Args:
        name (str): Name of the metadata type.
        checksum_types (dict): Checksum types for metadata and packages.
    Kwargs:
        default: The checksum type used if there is no specified nor original checksum type.
    """
    original = checksum_types.get("original")
    metadata = checksum_types.get("metadata")
    checksum_type = metadata if metadata else original.get(name, default)
    # "sha" -> "SHA" -> "CHECKSUM_TYPES.SHA" -> "sha1"
    normalized_checksum_type = getattr(CHECKSUM_TYPES, checksum_type.upper())
    return normalized_checksum_type


def cr_checksum_type_from_string(checksum_type):
    """
    Convert checksum type from string to createrepo_c enum variant.
    """
    # "sha1" -> "SHA1" -> "cr.SHA1"
    return getattr(cr, checksum_type.upper())


def publish(
    repository_version_pk,
    gpgcheck_options=None,
    metadata_signing_service=None,
    checksum_types=None,
    sqlite_metadata=False,
):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a publication from this repository version.
        gpgcheck_options (dict): GPG signature check options.
        metadata_signing_service (pulpcore.app.models.AsciiArmoredDetachedSigningService):
            A reference to an associated signing service.
        checksum_types (dict): Checksum types for metadata and packages.
        sqlite_metadata (bool): Whether to generate metadata files in sqlite format.

    """
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)
    repository = repository_version.repository.cast()
    checksum_types = checksum_types or {}

    if metadata_signing_service:
        metadata_signing_service = AsciiArmoredDetachedSigningService.objects.get(
            pk=metadata_signing_service
        )

    checksum_types["original"] = repository.original_checksum_types

    log.info(
        _("Publishing: repository={repo}, version={version}").format(
            repo=repository.name,
            version=repository_version.number,
        )
    )
    with tempfile.TemporaryDirectory(dir="."):
        with RpmPublication.create(repository_version) as publication:
            kwargs = {}
            first_package = repository_version.content.filter(
                pulp_type=Package.get_pulp_type()
            ).first()
            if first_package:
                kwargs["default"] = first_package.cast().checksum_type
            publication.metadata_checksum_type = get_checksum_type(
                "primary", checksum_types, **kwargs
            )
            publication.package_checksum_type = (
                checksum_types.get("package") or publication.metadata_checksum_type
            )

            if gpgcheck_options is not None:
                publication.gpgcheck = gpgcheck_options.get("gpgcheck")
                publication.repo_gpgcheck = gpgcheck_options.get("repo_gpgcheck")

            if sqlite_metadata:
                publication.sqlite_metadata = True

            publication_data = PublicationData(publication)
            publication_data.populate()

            total_repos = 1 + len(publication_data.sub_repos)
            pb_data = dict(
                message="Generating repository metadata",
                code="publish.generating_metadata",
                total=total_repos,
            )
            with ProgressReport(**pb_data) as publish_pb:
                content = publication.repository_version.content

                # Main repo
                generate_repo_metadata(
                    content,
                    publication,
                    checksum_types,
                    publication_data.repomdrecords,
                    metadata_signing_service=metadata_signing_service,
                )
                publish_pb.increment()

                for sub_repo in publication_data.sub_repos:
                    name = sub_repo[0]
                    checksum_types["original"] = getattr(publication_data, f"{name}_checksums")
                    content = getattr(publication_data, f"{name}_content")
                    extra_repomdrecords = getattr(publication_data, f"{name}_repomdrecords")
                    generate_repo_metadata(
                        content,
                        publication,
                        checksum_types,
                        extra_repomdrecords,
                        name,
                        metadata_signing_service=metadata_signing_service,
                    )
                    publish_pb.increment()

            log.info(_("Publication: {publication} created").format(publication=publication.pk))

            return publication


def generate_repo_metadata(
    content,
    publication,
    checksum_types,
    extra_repomdrecords,
    sub_folder=None,
    metadata_signing_service=None,
):
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

    if package_checksum_type and package_checksum_type not in settings.ALLOWED_CONTENT_CHECKSUMS:
        raise ValueError(
            "Repository contains disallowed package checksum type '{}', "
            "thus can't be published. {}".format(package_checksum_type, ALLOWED_CHECKSUM_ERROR_MSG)
        )

    # Prepare metadata files
    repomd_path = os.path.join(cwd, "repomd.xml")
    pri_xml_path = os.path.join(cwd, "primary.xml.gz")
    fil_xml_path = os.path.join(cwd, "filelists.xml.gz")
    oth_xml_path = os.path.join(cwd, "other.xml.gz")
    upd_xml_path = os.path.join(cwd, "updateinfo.xml.gz")
    mod_yml_path = os.path.join(cwd, "modules.yaml")
    comps_xml_path = os.path.join(cwd, "comps.xml")

    pri_xml = cr.PrimaryXmlFile(pri_xml_path)
    fil_xml = cr.FilelistsXmlFile(fil_xml_path)
    oth_xml = cr.OtherXmlFile(oth_xml_path)
    upd_xml = cr.UpdateInfoXmlFile(upd_xml_path)

    if publication.sqlite_metadata:
        pri_db_path = os.path.join(cwd, "primary.sqlite")
        fil_db_path = os.path.join(cwd, "filelists.sqlite")
        oth_db_path = os.path.join(cwd, "other.sqlite")
        pri_db = cr.PrimarySqlite(pri_db_path)
        fil_db = cr.FilelistsSqlite(fil_db_path)
        oth_db = cr.OtherSqlite(oth_db_path)

    packages = Package.objects.filter(pk__in=content)

    # We want to support publishing with a different checksum type than the one built-in to the
    # package itself, so we need to get the correct checksums somehow if there is an override.
    # We must also take into consideration that if the package has not been downloaded the only
    # checksum that is available is the one built-in.
    #
    # Since this lookup goes from Package->Content->ContentArtifact->Artifact, performance is a
    # challenge. We use ContentArtifact as our starting point because it enables us to work with
    # simple foreign keys and avoid messing with the many-to-many relationship, which doesn't
    # work with select_related() and performs poorly with prefetch_related(). This is fine
    # because we know that Packages should only ever have one artifact per content.
    contentartifact_qs = (
        ContentArtifact.objects.filter(content__in=packages.only("pk"))
        .select_related(
            # content__rpm_package is a bit of a hack, exploiting the way django sets up model
            # inheritance, but it works and is unlikely to break. All content artifacts being
            # accessed here have an associated Package since they originally came from the
            # Package queryset.
            "artifact",
            "content__rpm_package",
        )
        .only("artifact", "content__rpm_package__checksum_type", "content__rpm_package__pkgId")
    )

    pkg_to_hash = {}
    for ca in contentartifact_qs.iterator():
        if package_checksum_type:
            package_checksum_type = package_checksum_type.lower()
            pkgid = getattr(ca.artifact, package_checksum_type, None)

        if not package_checksum_type or not pkgid:
            if ca.content.rpm_package.checksum_type not in settings.ALLOWED_CONTENT_CHECKSUMS:
                raise ValueError(
                    "Package {} as content unit {} contains forbidden checksum type '{}', "
                    "thus can't be published. {}".format(
                        ca.content.rpm_package.nevra,
                        ca.content.pk,
                        ca.content.rpm_package.checksum_type,
                        ALLOWED_CHECKSUM_ERROR_MSG,
                    )
                )
            package_checksum_type = ca.content.rpm_package.checksum_type
            pkgid = ca.content.rpm_package.pkgId

        pkg_to_hash[ca.content_id] = (package_checksum_type, pkgid)

    # TODO: this is meant to be a !! *temporary* !! fix for
    # https://github.com/pulp/pulp_rpm/issues/2407
    pkg_pks_to_ignore = set()
    latest_build_time_by_nevra = defaultdict(list)
    for pkg in packages.only(
        "pk", "name", "epoch", "version", "release", "arch", "time_build"
    ).iterator():
        latest_build_time_by_nevra[pkg.nevra].append((pkg.time_build, pkg.pk))
    for nevra, pkg_data in latest_build_time_by_nevra.items():
        # sort the packages by when they were built
        if len(pkg_data) > 1:
            pkg_data.sort(key=lambda p: p[0], reverse=True)
            pkg_pks_to_ignore |= set(entry[1] for entry in pkg_data[1:])
            log.warning(
                "Duplicate packages found competing for NEVRA {nevra}, selected the one with "
                "the most recent build time, excluding {others} others.".format(
                    nevra=nevra, others=len(pkg_data[1:])
                )
            )

    total_packages = packages.count() - len(pkg_pks_to_ignore)

    pri_xml.set_num_of_pkgs(total_packages)
    fil_xml.set_num_of_pkgs(total_packages)
    oth_xml.set_num_of_pkgs(total_packages)

    # Process all packages
    for package in packages.order_by("name", "evr").iterator():
        if package.pk in pkg_pks_to_ignore:  # Temporary!
            continue
        pkg = package.to_createrepo_c()

        # rewrite the checksum and checksum type with the desired ones
        (checksum, pkgId) = pkg_to_hash[package.pk]
        pkg.checksum_type = checksum
        pkg.pkgId = pkgId

        pkg_filename = os.path.basename(package.location_href)
        # this can cause an issue when two same RPM package names appears
        # a/name1.rpm b/name1.rpm
        pkg.location_href = os.path.join(PACKAGES_DIRECTORY, pkg_filename[0].lower(), pkg_filename)
        pri_xml.add_pkg(pkg)
        fil_xml.add_pkg(pkg)
        oth_xml.add_pkg(pkg)
        if publication.sqlite_metadata:
            pri_db.add_pkg(pkg)
            fil_db.add_pkg(pkg)
            oth_db.add_pkg(pkg)

    # Process update records
    for update_record in UpdateRecord.objects.filter(pk__in=content).iterator():
        upd_xml.add_chunk(cr.xml_dump_updaterecord(update_record.to_createrepo_c()))

    # Process modulemd and modulemd_defaults
    with open(mod_yml_path, "ab") as mod_yml:
        for modulemd in Modulemd.objects.filter(pk__in=content).iterator():
            a = modulemd._artifacts.get()
            mod_yml.write(a.file.read())
            a.file.close()
            has_modules = True
        for default in ModulemdDefaults.objects.filter(pk__in=content).iterator():
            a = default._artifacts.get()
            mod_yml.write(a.file.read())
            a.file.close()
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

    comps.toxml_f(
        comps_xml_path,
        xml_options={
            "default_explicit": True,
            "empty_groups": True,
            "empty_packages": True,
            "uservisible_explicit": True,
        },
    )

    pri_xml.close()
    fil_xml.close()
    oth_xml.close()
    upd_xml.close()

    repomd = cr.Repomd()
    # If the repository is empty, use a revision of 0
    # See: https://pulp.plan.io/issues/9402
    if not content.exists():
        repomd.revision = "0"

    if publication.sqlite_metadata:
        repomdrecords = [
            ("primary", pri_xml_path, pri_db),
            ("filelists", fil_xml_path, fil_db),
            ("other", oth_xml_path, oth_db),
            ("primary_db", pri_db_path, None),
            ("filelists_db", fil_db_path, None),
            ("other_db", oth_db_path, None),
            ("updateinfo", upd_xml_path, None),
        ]
    else:
        repomdrecords = [
            ("primary", pri_xml_path, None),
            ("filelists", fil_xml_path, None),
            ("other", oth_xml_path, None),
            ("updateinfo", upd_xml_path, None),
        ]

    if has_modules:
        repomdrecords.append(("modules", mod_yml_path, None))

    if has_comps:
        repomdrecords.append(("group", comps_xml_path, None))

    repomdrecords.extend(extra_repomdrecords)

    sqlite_files = ("primary_db", "filelists_db", "other_db")

    for name, path, db_to_update in repomdrecords:
        record = cr.RepomdRecord(name, path)
        checksum_type = cr_checksum_type_from_string(
            get_checksum_type(name, checksum_types, default=publication.metadata_checksum_type)
        )
        if name in sqlite_files:
            record_bz = record.compress_and_fill(checksum_type, cr.BZ2)
            record_bz.type = name
            record_bz.rename_file()
            path = record_bz.location_href.split("/")[-1]
            repomd.set_record(record_bz)
        else:
            record.fill(checksum_type)
            if db_to_update:
                db_to_update.dbinfo_update(record.checksum)
                db_to_update.close()
            record.rename_file()
            path = record.location_href.split("/")[-1]
            repomd.set_record(record)

        if sub_folder:
            path = os.path.join(sub_folder, path)

        with open(path, "rb") as repodata_fd:
            PublishedMetadata.create_from_file(
                relative_path=os.path.join(repodata_path, os.path.basename(path)),
                publication=publication,
                file=File(repodata_fd),
            )

    with open(repomd_path, "w") as repomd_f:
        repomd_f.write(repomd.xml_dump())

    if metadata_signing_service:
        signing_service = AsciiArmoredDetachedSigningService.objects.get(
            pk=metadata_signing_service
        )
        sign_results = signing_service.sign(repomd_path)

        # publish a signed file
        with open(sign_results["file"], "rb") as signed_file_fd:
            PublishedMetadata.create_from_file(
                relative_path=os.path.join(repodata_path, os.path.basename(sign_results["file"])),
                publication=publication,
                file=File(signed_file_fd),
            )

        # publish a detached signature
        with open(sign_results["signature"], "rb") as signature_fd:
            PublishedMetadata.create_from_file(
                relative_path=os.path.join(
                    repodata_path, os.path.basename(sign_results["signature"])
                ),
                publication=publication,
                file=File(signature_fd),
            )

        # publish a public key required for further verification
        pubkey_name = "repomd.xml.key"
        with open(pubkey_name, "wb+") as f:
            f.write(signing_service.public_key.encode("utf-8"))
            f.flush()
            # important! as the file has already been opened and used, it will be treated as a
            # cursor and when calculating the checksum it will calculate the checksum of nothing.
            f.seek(0)
            PublishedMetadata.create_from_file(
                relative_path=os.path.join(repodata_path, pubkey_name),
                publication=publication,
                file=File(f),
            )
    else:
        with open(repomd_path, "rb") as repomd_fd:
            PublishedMetadata.create_from_file(
                relative_path=os.path.join(repodata_path, os.path.basename(repomd_path)),
                publication=publication,
                file=File(repomd_fd),
            )
