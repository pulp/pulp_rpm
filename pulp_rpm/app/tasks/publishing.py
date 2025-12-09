import logging
import os
import shutil
import tempfile
from gettext import gettext as _
from typing import NamedTuple
from uuid import UUID

import createrepo_c as cr
import libcomps
from django.conf import settings
from django.core.files import File
from django.db.models import Q
from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    ContentArtifact,
    ProgressReport,
    PublishedArtifact,
    PublishedMetadata,
    RepositoryContent,
    RepositoryVersion,
)

from pulp_rpm.app.comps import dict_to_strdict
from pulp_rpm.app.constants import (
    ALLOWED_CHECKSUM_ERROR_MSG,
    CHECKSUM_TYPES,
    COMPRESSION_TYPES,
    LAYOUT_TYPES,
    PACKAGES_DIRECTORY,
)
from pulp_rpm.app.kickstart.treeinfo import PulpTreeInfo, TreeinfoData
from pulp_rpm.app.models import (
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    ModulemdObsolete,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RepoMetadataFile,
    RpmPublication,
    UpdateRecord,
)
from pulp_rpm.app.serializers import RpmPublicationSerializer
from pulp_rpm.app.shared_utils import format_nevra

log = logging.getLogger(__name__)

REPODATA_PATH = "repodata"

# lift dynaconf lookups outside of loops
ALLOWED_CONTENT_CHECKSUMS = settings.ALLOWED_CONTENT_CHECKSUMS
RPM_METADATA_USE_REPO_PACKAGE_TIME = settings.RPM_METADATA_USE_REPO_PACKAGE_TIME


class PackageInfo(NamedTuple):
    """
    Data about a package being published that needs to be shared with the repo metadata.

    Attributes:
        caid (UUID): ContentArtifact ID.
        path (str): The relative URL where the package will be published.
        checksum_type (str): The type (eg. sha256) of the checksum.
        checksum (str): The checksum value of the package.

    """

    caid: UUID
    path: str
    checksum_type: str
    checksum: str


class PkgBuild(NamedTuple):
    """
    Data about a package build for collision resolution.

    Attributes:
        cid (UUID): Content ID.
        epoch (int): The Epoch of the package build.
        build_time (int): The build time (unix timestamp format) of the package.

    """

    cid: UUID
    epoch: int
    build_time: int


class _CollisionManager:
    """Helper to collect the "winning" packages when there are collisions on NEVRA or URL path."""

    def __init__(self) -> None:
        self.cid_to_second_path: dict[UUID, str] = {}
        self._nevra_to_pkg: dict[str, PkgBuild] = {}
        self._path_to_pkg: dict[str, PkgBuild] = {}
        self._second_path_to_pkg: dict[str, PkgBuild] = {}
        self._banned_cids: set[UUID] = set()

    def _pkg_to_ignore(
        self, new: PkgBuild, index_to_pkg: dict[str, PkgBuild], index: str
    ) -> PkgBuild | None:
        old = index_to_pkg.get(index, None)
        if not old or old.cid in self._banned_cids:
            return None

        log.warning(
            _(
                "Duplicate packages found competing for {index}, selected the one with "
                "the most recent epoch or build time."
            ).format(index=index)
        )
        if old.epoch > new.epoch or (old.epoch == new.epoch and old.build_time >= new.build_time):
            return new
        return old

    def add(self, pkg: PkgBuild, nevra: str, path: str, second_path: str | None) -> None:
        """
        Add a package build to the collision manager. Ignore it if it is "worse" than an existing
        package that collides on nevra or path. If it's "better" and collides, mark the older one as
        ignored so it will not be included when `retained_cids` is called.

        Args:
            pkg (PkgBuild): Information about the package build we're adding.
            nevra (str): NEVRA of the package. Checked for collisions in repo metadata.
            path (str): URL path of the package. Checked for collisions in published artifact URLs.
            second_path (str | None):
                An optional secondary URL path of the package. Only will exist in the nested_by_both
                case. Checked for collisions like `path`, except collisions here only prevent the
                "worse" package from being published at this secondary path, not from being
                published at in general.
        """
        # If there is a collision on nevra or path, ignore the older package
        to_ignore_nevra = self._pkg_to_ignore(pkg, self._nevra_to_pkg, nevra)
        to_ignore_path = self._pkg_to_ignore(pkg, self._path_to_pkg, path)

        if to_ignore_nevra == pkg or to_ignore_path == pkg:
            return  # Just ignore it before it's added anywhere.

        # Else remember it.
        self._nevra_to_pkg[nevra] = pkg
        self._path_to_pkg[path] = pkg

        # We have record cids that were once added but later ignored; we don't know all its keys.
        if to_ignore_nevra:
            self._banned_cids.add(to_ignore_nevra.cid)
            self.cid_to_second_path.pop(to_ignore_nevra.cid, None)
        if to_ignore_path:
            self._banned_cids.add(to_ignore_path.cid)
            self.cid_to_second_path.pop(to_ignore_path.cid, None)

        # In the nested_by_both case we may have a package that should be published in general, but
        # collides on the alphabetical path and should be ignored for that path only.
        if second_path:
            to_ignore = self._pkg_to_ignore(pkg, self._second_path_to_pkg, second_path)
            if to_ignore == pkg:
                return
            elif to_ignore:
                self.cid_to_second_path.pop(to_ignore.cid, None)

            self._second_path_to_pkg[second_path] = pkg
            self.cid_to_second_path[pkg.cid] = second_path

    def retained_cids(self) -> list[UUID]:
        """
        Return a list of retained Content IDs, excluding those that collide on NEVRA or Path.

        Returns:
            list: List of Content IDs that should be published.
        """
        return [pkg.cid for pkg in self._nevra_to_pkg.values() if pkg.cid not in self._banned_cids]


class PublicationData:
    """
    Encapsulates data relative to publication.

    Attributes:
        publication (pulpcore.plugin.models.Publication): A Publication to populate.
        sub_repos (list): A list of tuples with sub_repos data.
        repomdrecords (list): A list of tuples with repomdrecords data.

    """

    def __init__(self, publication, checksum_types):
        """
        Setting Publication data.

        Args:
            publication (pulpcore.plugin.models.Publication): A Publication to populate.

        """
        self.publication = publication
        self.sub_repos = []
        self.repomdrecords = []
        self.checksum_types = checksum_types
        self.packages: dict[UUID, PackageInfo] = {}

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
                repomdrecords.append((repo_metadata_file.data_type, new_file.name))

        return repomdrecords

    def publish_artifacts(self, content, prefix=""):
        """
        Create PublishedArtifacts for each Artifact. Special considerations for Packages:

        1. Respect the layout of the publication.
           1. "flat": "Packages/xxx.rpm"
           2. "nested_alphabetically": "Packages/n/name.rpm"   - The "canonical" repo format.
           3. "nested_by_digest": "Packages/hh/hhhh/xxx.rpm"
           4. "nested_by_both": Both 2 and 3. Each rpm will result in 2 PublishedArtifacts.

        2. Handle "duplicate" packages.

           There are two ways that different packages (different checksums) can "collide":
              a) Packages with the same NEVRA (Name, Epoch, Version, Release, Arch) will
                 collide in the repo metadata. One of them will "win" in the client. This can be the
                 case if a signed and unsigned package are both published in the same repo for
                 example, but also if people just reuse NEVRAs for different builds.
              b) Packages that result in the same URL will collide at the http level. This can be
                 different from case A if they are not using the NEVRA format for relative_path.
                 They may not have anywhere close to the same NEVRA, just the same filename.

           In both cases we have to pick one - which is essentially what the rest of the RPM
           Ecosystem does when faced with the impossible. This code takes the one with the
           most recent build time which is the same heuristic used by Yum/DNF/Zypper. The "winner"
           package must be consistent here and when writing the repo metadata later.

        3. Use the correct hash for artifacts.

           We want to support publishing with a different checksum type than the one built-in to
           the package itself, so we need to get the correct checksums somehow if there is an
           override. We must also take into consideration that if the package has not been
           downloaded the only checksum that is available is the one built-in.

           Since this lookup goes from Package->Content->ContentArtifact->Artifact, performance is
           a challenge. We use ContentArtifact as our starting point because it enables us to work
           with simple foreign keys and avoid messing with the many-to-many relationship, which
           doesn't work with select_related() and performs poorly with prefetch_related(). This is
           fine because we know that Packages should only ever have one artifact per content.

        All three of these considerations are relevant both here when creating the
        PublishedArtifacts, as well as later when generating the repo metadata that references them.
        Do these things once here and record the info for use later to avoid lots of redundant
        lookups, as well as guarantee we're making the same decisions in both places.

        Note that this only impacts user-created publications, which produce the "standard"
        RPM layout of repo/Packages/f/foo.rpm. A publication created by mirror-sync retains
        whatever layout their "upstream" repo-metadata dictates.

        Args:
            content (pulpcore.plugin.models.Content): content set.
            prefix (str): a relative path prefix for the published artifact

        Returns:
            dict: Mapping of content_id to PackageInfo for retained packages.
        """

        def nested_alphabetically_path(pkg_filename):
            """Returns the path to use for nested_alphabetically. Used twice, define once."""
            return os.path.join(PACKAGES_DIRECTORY, pkg_filename[0].lower(), pkg_filename)

        def nested_by_digest_path(pkg_filename, checksum):
            """Returns the path to use for nested_by_digest. Used twice, define once."""
            # Regardless of checksum type, let's use the first 6 characters of the checksum
            # to create a nested directory structure.
            if len(checksum) < 6:
                raise ValueError(
                    f"Checksum {checksum} is unknown or too short to use for "
                    f"{layout} publishing."
                )
            return os.path.join(PACKAGES_DIRECTORY, checksum[:2], checksum[2:6], pkg_filename)

        def flat_path(pkg_filename):
            """Returns the path to use for flat layout. Define to keep it close to the others."""
            return os.path.join(PACKAGES_DIRECTORY, pkg_filename)

        published_artifacts = []
        requested_checksum_type = get_checksum_type(self.checksum_types)
        layout = self.publication.layout
        collision_manager = _CollisionManager()
        cid_to_pkginfo: dict[UUID, PackageInfo] = {}

        # Special Handling for Packages first
        contentartifact_qs = ContentArtifact.objects.filter(content__in=content).filter(
            content__pulp_type=Package.get_pulp_type()
        )

        fields = [
            "pk",
            "content_id",
            "relative_path",
            "content__rpm_package__checksum_type",
            "content__rpm_package__pkgId",
            "content__rpm_package__name",
            "content__rpm_package__epoch",
            "content__rpm_package__version",
            "content__rpm_package__release",
            "content__rpm_package__arch",
            "content__rpm_package__time_build",
        ]
        artifact_checksum = None
        if requested_checksum_type:
            artifact_checksum = f"artifact__{requested_checksum_type}"
            fields.append(artifact_checksum)

        for row in contentartifact_qs.values(*fields).iterator():
            # content_id is the same as the Package PK, which is used later when generating repo
            # metadata. The contentartifact PK is different, and is used here for PublishedArtifact.
            # There is no such thing as a multi-Artifact RPM Package, so in practice these are 1:1,
            # even though that's not enforced at the DB level. (There _are_ multi-Artifact Contents
            # in general, such as deb src packages - where one logical Content maps to three actual
            # files, and a unique file may appear in any number of deb src packages - so pulpcore
            # allows a many-to-many relationship. But this is not applicable to RPM Packages.)

            # First, get some basic package data
            caid = row["pk"]
            cid = row["content_id"]
            build_time = row["content__rpm_package__time_build"]
            epoch = row["content__rpm_package__epoch"]
            nevra = format_nevra(
                row["content__rpm_package__name"],
                epoch,
                row["content__rpm_package__version"],
                row["content__rpm_package__release"],
                row["content__rpm_package__arch"],
            )
            epoch = int(epoch) if epoch else 0  # epoch is always an int if defined
            pkg_build = PkgBuild(cid=cid, epoch=epoch, build_time=build_time)

            # Second, get the checksum / checksum type, defaulting to rpm_package__pkgId if needed
            if requested_checksum_type:
                checksum = row.get(artifact_checksum, None)
                checksum_type = requested_checksum_type

            if not requested_checksum_type or not checksum:
                checksum = row["content__rpm_package__pkgId"]
                checksum_type = row["content__rpm_package__checksum_type"]
                if checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
                    raise ValueError(
                        "Package with pkgId {} as content unit {} contains forbidden checksum type "
                        "'{}', thus can't be published. {}".format(
                            checksum,
                            cid,
                            checksum_type,
                            ALLOWED_CHECKSUM_ERROR_MSG,
                        )
                    )

            # Third, compute the path based on layout
            pkg_filename = os.path.basename(row["relative_path"])
            second_path = None
            if layout == LAYOUT_TYPES.NESTED_ALPHABETICALLY:
                path = nested_alphabetically_path(pkg_filename)
            elif layout == LAYOUT_TYPES.FLAT:
                path = flat_path(pkg_filename)
            elif layout == LAYOUT_TYPES.NESTED_BY_DIGEST:
                path = nested_by_digest_path(pkg_filename, checksum)
            elif layout == LAYOUT_TYPES.NESTED_BY_BOTH:
                path = nested_by_digest_path(pkg_filename, checksum)
                second_path = nested_alphabetically_path(pkg_filename)
            else:
                raise ValueError(f"Layout value {layout} is unsupported by this version")

            pkg_info = PackageInfo(
                caid=caid, path=path, checksum_type=checksum_type, checksum=checksum
            )
            collision_manager.add(pkg_build, nevra, path, second_path)
            cid_to_pkginfo[cid] = pkg_info

        # Filter cid_to_pkginfo to only the retained packages
        retained_cids = collision_manager.retained_cids()
        cid_to_pkginfo = {k: cid_to_pkginfo[k] for k in retained_cids}

        # Finally create the PublishedArtifacts for the remaining packages
        for cid, pkg_info in cid_to_pkginfo.items():
            published_artifacts.append(
                PublishedArtifact(
                    relative_path=os.path.join(prefix, pkg_info.path),
                    publication=self.publication,
                    content_artifact_id=pkg_info.caid,
                )
            )
            if second_path := collision_manager.cid_to_second_path.get(cid, None):
                # also add the nested_alphabetically path
                published_artifacts.append(
                    PublishedArtifact(
                        relative_path=os.path.join(prefix, second_path),
                        publication=self.publication,
                        content_artifact_id=pkg_info.caid,
                    )
                )

        # Handle the non-packages
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
        return cid_to_pkginfo

    def handle_sub_repos(self, distribution_tree):
        """
        Get sub-repo content and publish them.

        Args:
            distribution_tree (pulp_rpm.models.DistributionTree): A distribution_tree object.

        """
        original_treeinfo_content_artifact = distribution_tree.contentartifact_set.get(
            relative_path__in=[".treeinfo", "treeinfo"]
        )
        orig_artifact = original_treeinfo_content_artifact.artifact
        artifact_file = orig_artifact.pulp_domain.get_storage().open(orig_artifact.file.name)
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
                        )
                    )

    def populate(self):
        """
        Populate a publication.

        Create published artifacts for a publication.

        """
        main_content = self.publication.repository_version.content
        self.repomdrecords = self.prepare_metadata_files(main_content)

        self.packages = self.publish_artifacts(main_content)

        distribution_trees = DistributionTree.objects.filter(pk__in=main_content).prefetch_related(
            "addons",
            "variants",
            "addons__repository",
            "variants__repository",
            "contentartifact_set",
        )

        for distribution_tree in distribution_trees:
            self.handle_sub_repos(distribution_tree)

        for name, content in self.sub_repos:
            os.mkdir(name)
            setattr(self, f"{name}_content", content)
            setattr(self, f"{name}_checksums", self.checksum_types)
            setattr(self, f"{name}_repomdrecords", self.prepare_metadata_files(content, name))
            setattr(self, f"{name}_packages", self.publish_artifacts(content, prefix=name))


def get_checksum_type(checksum_types, default=CHECKSUM_TYPES.SHA256):
    """
    Get checksum algorithm for publishing metadata.

    Args:
        checksum_types (dict): Checksum types for metadata and packages.
    Kwargs:
        default: The checksum type used if there is no specified nor original checksum type.
    """
    general = checksum_types.get("general")
    metadata = checksum_types.get("metadata")
    # fallback order
    checksum_type = general or metadata or default
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
    metadata_signing_service=None,
    checkpoint=False,
    checksum_types=None,
    checksum_type=None,
    repo_config=None,
    compression_type=COMPRESSION_TYPES.GZ,
    layout=None,
    *args,
    **kwargs,
):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a publication from this repository version.
        metadata_signing_service (pulpcore.app.models.AsciiArmoredDetachedSigningService):
            A reference to an associated signing service.
        checkpoint (bool): Whether to create a checkpoint publication.
        checksum_types (dict): Checksum types for metadata and packages.
        repo_config (JSON): repo config that will be served by distribution
        compression_type(pulp_rpm.app.constants.COMPRESSION_TYPES):
            Compression type to use for metadata files.
        layout(pulp_rpm.app.constants.LAYOUT_TYPES):
            How to layout the package files within the publication (flat, nested, etc.)

    """
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)
    repository = repository_version.repository.cast()
    checksum_types = checksum_types or {}
    # currently unused, but prep for eliminating "checksum_types due to zero-downtime requirements"
    if checksum_type:
        checksum_types = {"general": checksum_type}

    if metadata_signing_service:
        metadata_signing_service = AsciiArmoredDetachedSigningService.objects.get(
            pk=metadata_signing_service
        )

    if layout is None:
        # Can't simply set a default in the function signature because some code calls this function
        # with an explicit None value.
        layout = LAYOUT_TYPES.NESTED_ALPHABETICALLY

    log.info(
        _("Publishing: repository={repo}, version={version}").format(
            repo=repository.name,
            version=repository_version.number,
        )
    )
    with tempfile.TemporaryDirectory(dir="."):
        with RpmPublication.create(repository_version, checkpoint=checkpoint) as publication:
            checksum_type = get_checksum_type(checksum_types)
            publication.checksum_type = checksum_type
            publication.compression_type = compression_type
            publication.layout = layout
            publication.repo_config = repo_config

            publication_data = PublicationData(publication, checksum_types)
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
                    compression_type=compression_type,
                    retained_packages=publication_data.packages,
                )
                publish_pb.increment()

                for sub_repo in publication_data.sub_repos:
                    name = sub_repo[0]
                    content = getattr(publication_data, f"{name}_content")
                    extra_repomdrecords = getattr(publication_data, f"{name}_repomdrecords")
                    packages = getattr(publication_data, f"{name}_packages")
                    generate_repo_metadata(
                        content,
                        publication,
                        checksum_types,
                        extra_repomdrecords,
                        name,
                        metadata_signing_service=metadata_signing_service,
                        compression_type=compression_type,
                        retained_packages=packages,
                    )
                    publish_pb.increment()

            log.info(_("Publication: {publication} created").format(publication=publication.pk))
            serialized_pub = RpmPublicationSerializer(
                instance=publication, context={"request": None}
            ).data
            return serialized_pub


def generate_repo_metadata(
    content,
    publication,
    checksum_types,
    extra_repomdrecords,
    sub_folder=None,
    metadata_signing_service=None,
    compression_type=COMPRESSION_TYPES.GZ,
    retained_packages: dict[UUID, PackageInfo] = {},
):
    """
    Creates a repomd.xml file.

    Args:
        content(app.models.Content): A DB Content set of all original artifacts in the publication.
        publication(pulpcore.plugin.models.Publication): the publication
        extra_repomdrecords(list): list with data relative to repo metadata files
        sub_folder(str): name of the folder for sub repos
        metadata_signing_service (pulpcore.app.models.AsciiArmoredDetachedSigningService):
            A reference to an associated signing service.
        compression_type(pulp_rpm.app.constants.COMPRESSION_TYPES):
            Compression type to use for metadata files.
        retained_packages(dict):
            A dictionary of content_id to PackageInfo for packages that should actually be included
            in the repository metadata. Will be used to filter `content` and add additional info.

    """
    cwd = os.getcwd()
    repodata_path = REPODATA_PATH
    has_modules = False
    has_comps = False
    requested_checksum_type = get_checksum_type(checksum_types)

    if requested_checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
        raise ValueError(
            "Disallowed checksum type '{}' was requested to be used for publication: {}".format(
                requested_checksum_type, ALLOWED_CHECKSUM_ERROR_MSG
            )
        )

    if sub_folder:
        cwd = os.path.join(cwd, sub_folder)
        repodata_path = os.path.join(sub_folder, repodata_path)

    # Prepare metadata files
    cr_compression_type = cr.ZSTD if compression_type == COMPRESSION_TYPES.ZSTD else cr.GZ
    total_packages = len(retained_packages)

    if RPM_METADATA_USE_REPO_PACKAGE_TIME:
        # gather the times the packages were added to the repo
        repo_content = (
            RepositoryContent.objects.filter(
                repository=publication.repository,
                version_added__number__lte=publication.repository_version.number,
            )
            .exclude(version_removed__number__lte=publication.repository_version.number)
            .values_list("content", "pulp_created")
        )
        repo_pkg_times = {pk: created.timestamp() for pk, created in repo_content}

    repomd_path = os.path.join(repodata_path, "repomd.xml")
    mod_yml_path = os.path.join(repodata_path, "modules.yaml")
    comps_xml_path = os.path.join(repodata_path, "comps.xml")

    cr_checksum_type = cr_checksum_type_from_string(publication.checksum_type)

    # Process all packages
    with cr.RepositoryWriter(
        cwd, compression=cr_compression_type, checksum_type=cr_checksum_type
    ) as writer:
        writer.set_num_of_pkgs(total_packages)

        # If the repository is empty, use a revision of 0
        # See: https://pulp.plan.io/issues/9402
        if not content.exists():
            writer.repomd.revision = "0"
        for package in Package.objects.filter(pk__in=content).order_by("name", "evr").iterator():
            if package.pk not in retained_packages:
                continue
            pkg = package.to_createrepo_c()

            # rewrite these fields with the desired ones
            retained_pkg_info = retained_packages[package.pk]
            pkg.checksum_type = retained_pkg_info.checksum_type
            pkg.pkgId = retained_pkg_info.checksum
            pkg.location_href = retained_pkg_info.path

            if RPM_METADATA_USE_REPO_PACKAGE_TIME:
                pkg.time_file = repo_pkg_times[package.pk]

            writer.add_pkg(pkg)

        # Process update records
        update_records = UpdateRecord.objects.filter(pk__in=content).order_by("id", "digest")
        for update_record in update_records.iterator():
            writer.add_update_record(update_record.to_createrepo_c())

        # Process modulemd, modulemd_defaults and obsoletes
        with open(mod_yml_path, "ab") as mod_yml:
            modulemds = Modulemd.objects.filter(pk__in=content).order_by(
                *Modulemd.natural_key_fields()
            )
            for modulemd in modulemds.iterator():
                mod_yml.write(modulemd.snippet.encode())
                mod_yml.write(b"\n")
                has_modules = True
            modulemd_defaults = ModulemdDefaults.objects.filter(pk__in=content).order_by(
                *ModulemdDefaults.natural_key_fields()
            )
            for default in modulemd_defaults.iterator():
                mod_yml.write(default.snippet.encode())
                mod_yml.write(b"\n")
                has_modules = True
            modulemd_obsoletes = ModulemdObsolete.objects.filter(pk__in=content).order_by(
                *ModulemdObsolete.natural_key_fields()
            )
            for obsolete in modulemd_obsoletes.iterator():
                mod_yml.write(obsolete.snippet.encode())
                mod_yml.write(b"\n")
                has_modules = True

        # Process comps
        comps = libcomps.Comps()
        for pkg_grp in PackageGroup.objects.filter(pk__in=content).order_by("id").iterator():
            group = pkg_grp.pkg_grp_to_libcomps()
            comps.groups.append(group)
            has_comps = True
        for pkg_cat in PackageCategory.objects.filter(pk__in=content).order_by("id").iterator():
            cat = pkg_cat.pkg_cat_to_libcomps()
            comps.categories.append(cat)
            has_comps = True
        for pkg_env in PackageEnvironment.objects.filter(pk__in=content).order_by("id").iterator():
            env = pkg_env.pkg_env_to_libcomps()
            comps.environments.append(env)
            has_comps = True
        package_langpacks = PackageLangpacks.objects.filter(pk__in=content).order_by(
            *PackageLangpacks.natural_key_fields()
        )
        for pkg_lng in package_langpacks.iterator():
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

        if has_modules:
            writer.add_repomd_metadata("modules", mod_yml_path, use_compression=False)

        if has_comps:
            writer.add_repomd_metadata("group", comps_xml_path, use_compression=False)

        for name, record in extra_repomdrecords:
            writer.add_repomd_metadata(name, record)

    for record in writer.repomd.records:
        path = os.path.join(repodata_path, os.path.basename(record.location_href))
        with open(path, "rb") as repodata_fd:
            PublishedMetadata.create_from_file(
                relative_path=path,
                publication=publication,
                file=File(repodata_fd),
            )

    if metadata_signing_service:
        signing_service = AsciiArmoredDetachedSigningService.objects.get(
            pk=metadata_signing_service
        )
        sign_results = signing_service.sign(repomd_path)

        # https://github.com/pulp/pulp_rpm/issues/3526
        signature_file_path = sign_results["signature"]
        if os.stat(signature_file_path).st_size == 0:
            log.error(f"{signature_file_path} is 0 bytes! sign_results: {sign_results}")
            raise Exception("Signature file is 0 bytes")

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
