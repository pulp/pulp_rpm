import gzip
import hashlib
import logging
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from gettext import gettext as _
from typing import NamedTuple
from uuid import UUID

import createrepo_c as cr
from django.conf import settings
from django.core.files import File
from django.db import IntegrityError
from django.db.models import Count, Q

from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    Content,
    ContentArtifact,
    ProgressReport,
    PublishedArtifact,
    PublishedMetadata,
    RepositoryContent,
    RepositoryVersion,
)

from pulp_rpm.app.comps import models_to_comps_data
from pulp_rpm.app.constants import (
    ALLOWED_CHECKSUM_ERROR_MSG,
    CHECKSUM_TYPES,
    COMPRESSION_TYPES,
    LAYOUT_TYPES,
    PACKAGES_DIRECTORY,
)
from pulp_rpm.app.exceptions import (
    ChecksumTooShortError,
    ForbiddenChecksumTypeError,
    MetadataSigningError,
    UnsupportedLayoutError,
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
from pulp_rpm.app.sql_utils import safe_in

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
        self._nevra_to_pkg: dict[str, PkgBuild] = {}
        self._path_to_pkg: dict[str, PkgBuild] = {}
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

    def add(self, pkg: PkgBuild, nevra: str, path: str) -> None:
        """
        Add a package build to the collision manager. Ignore it if it is "worse" than an existing
        package that collides on nevra or path. If it's "better" and collides, mark the older one as
        ignored so it will not be included when `retained_cids` is called.

        Args:
            pkg (PkgBuild): Information about the package build we're adding.
            nevra (str): NEVRA of the package. Checked for collisions in repo metadata.
            path (str): URL path of the package. Checked for collisions in published artifact URLs.
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
        if to_ignore_path:
            self._banned_cids.add(to_ignore_path.cid)

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

    @staticmethod
    def _publication_path(path):
        """Return a path contained by the publication working directory."""
        publication_root = os.path.realpath(".")
        target = os.path.realpath(path)
        if os.path.commonpath((publication_root, target)) != publication_root:
            raise ValueError(f"Path outside publication working directory: {path}")
        return target

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
            path = self._publication_path(path)
            with open(path, "wb") as new_file:
                shutil.copyfileobj(current_file, new_file)
                repomdrecords.append((repo_metadata_file.data_type, new_file.name))

        return repomdrecords

    def publish_artifacts(self, content, prefix=""):
        """
        Create PublishedArtifacts for each Artifact. Special considerations for Packages:

        1. Respect the layout of the publication.
           1. "flat": "Packages/xxx.rpm"
           2. "nested_alphabetically": "Packages/f/filename.rpm"   - The "canonical" repo format.
           3. "nested_by_digest": "Packages/f/by-digest/xxxxxx-filename.rpm"

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
            checksum, checksum_type = _package_checksum(
                row, requested_checksum_type, artifact_checksum
            )

            # Third, compute the path based on layout
            pkg_filename = os.path.basename(row["relative_path"])
            path = _published_path(layout, pkg_filename, checksum)

            pkg_info = PackageInfo(
                caid=caid, path=path, checksum_type=checksum_type, checksum=checksum
            )
            collision_manager.add(pkg_build, nevra, path)
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

        # Handle the non-packages
        is_treeinfo = Q(relative_path__in=["treeinfo", ".treeinfo"])
        unpublishable_types = Q(content__pulp_type__in=_UNPUBLISHABLE_TYPES)

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
            os.mkdir(self._publication_path(name))
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


@dataclass(frozen=True)
class PublishRequest:
    """A validated publish request, with every setting already resolved."""

    repository_version: RepositoryVersion
    metadata_signing_service: AsciiArmoredDetachedSigningService | None = None
    checkpoint: bool = False
    checksum_types: dict = field(default_factory=dict)
    compression_type: str = COMPRESSION_TYPES.GZ
    layout: str = LAYOUT_TYPES.NESTED_ALPHABETICALLY
    repo_config: dict | None = None

    @property
    def checksum_type(self):
        """The checksum type used for metadata files."""
        return get_checksum_type(self.checksum_types)


@dataclass(frozen=True)
class ContentDelta:
    """The content a version adds to and removes from its base version."""

    added_pks: frozenset = frozenset()
    removed_pks: frozenset = frozenset()
    changed_types: frozenset = frozenset()


@dataclass(frozen=True)
class PublishPlan:
    """What was decided about a publish request, before anything is written."""

    request: PublishRequest
    base_publication: RpmPublication | None
    delta: ContentDelta = ContentDelta()

    @property
    def derived(self):
        return self.base_publication is not None


class PublicationPlanner:
    """Decide whether the requested publication can be derived from an existing one."""

    def __init__(self, request):
        self.request = request

    def plan(self):
        """Build the plan for the request."""
        base = self._base_publication()
        if base is None:
            return PublishPlan(self.request, None)
        version = self.request.repository_version
        delta = self._delta(base)
        reason = self._incompatibility(base) or self._delta_reason(version, delta)
        if reason:
            log.warning(
                _("Not deriving the publication of {version} from {base}: {reason}").format(
                    version=version, base=base.pk, reason=reason
                )
            )
            return PublishPlan(self.request, None)
        return PublishPlan(self.request, base, delta)

    def _base_publication(self):
        """The newest complete publication of the same repository this one can reuse.

        Only publications built with the same settings are candidates, so a repository that
        alternates settings still derives from its most recent compatible publication.
        """
        request = self.request
        version = request.repository_version
        return (
            RpmPublication.objects.filter(
                repository_version__repository_id=version.repository_id,
                repository_version__number__lte=version.number,
                complete=True,
                checkpoint=request.checkpoint,
                checksum_type=request.checksum_type,
                compression_type=request.compression_type,
                layout=request.layout,
                repo_config=request.repo_config or {},
                metadata_signing_fingerprint=_signing_fingerprint(request.metadata_signing_service),
                metadata_fingerprints__isnull=False,
            )
            .select_related("repository_version")
            .defer("repository_version__content_ids")
            .order_by("-repository_version__number", "-pulp_created")
            .first()
        )

    def _delta(self, base):
        """The content the target version adds to and removes from the base version."""
        version = self.request.repository_version
        if base.repository_version_id == version.pk:
            return ContentDelta()
        added = frozenset(version.added(base.repository_version).values_list("pk", flat=True))
        removed = frozenset(version.removed(base.repository_version).values_list("pk", flat=True))
        return ContentDelta(added, removed, _changed_pulp_types(added, removed))

    @staticmethod
    def _delta_reason(version, delta):
        """Return why the delta makes deriving pointless, or None if it does not."""
        if (delta.added_pks or delta.removed_pks) and not PublicationPlanner._worth_deriving(
            version.content.count(), len(delta.added_pks), len(delta.removed_pks)
        ):
            return "the delta is too large"
        if DistributionTree.get_pulp_type() in delta.changed_types:
            return "it contains distribution trees"
        return None

    @staticmethod
    def _worth_deriving(target, added, removed):
        """Deriving pays off while most of both the target and the base content are retained."""
        retained = target - added
        return added <= retained and removed <= retained

    def _incompatibility(self, base):
        """Return why the base publication cannot be derived from, or None if it can."""
        settings = (base.metadata_fingerprints or {}).get("settings") or {}
        if settings.get("format") != _METADATA_FORMAT:
            return "metadata format differs or is unknown"
        if settings.get("repository_package_time") != RPM_METADATA_USE_REPO_PACKAGE_TIME:
            return "RPM_METADATA_USE_REPO_PACKAGE_TIME differs or is unknown"
        if _has_distribution_trees(base.repository_version):
            return "base repository version contains distribution trees"
        return None


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
            How to layout the package files within the publication (flat, nested, etc.).

    """
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)
    checksum_types = checksum_types or {}
    # currently unused, but prep for eliminating "checksum_types due to zero-downtime requirements"
    if checksum_type:
        checksum_types = {"general": checksum_type}

    if metadata_signing_service:
        metadata_signing_service = AsciiArmoredDetachedSigningService.objects.get(
            pk=metadata_signing_service
        )

    request = PublishRequest(
        repository_version=repository_version,
        metadata_signing_service=metadata_signing_service,
        checkpoint=checkpoint,
        checksum_types=checksum_types,
        compression_type=compression_type,
        layout=layout or LAYOUT_TYPES.NESTED_ALPHABETICALLY,
        repo_config=repo_config,
    )
    return apply_publish(PublicationPlanner(request).plan())


def apply_publish(plan):
    """Create the publication the plan describes."""
    if not plan.derived:
        return _publish_full(plan)
    try:
        return _publish_derived(plan)
    except (
        _CannotDerive,
        RpmPublication.DoesNotExist,
        PublishedMetadata.DoesNotExist,
        cr.CreaterepoCError,
        IntegrityError,
        OSError,
        UnicodeDecodeError,
    ) as exc:
        log.warning(
            _("Not deriving the publication of {version}: {reason}").format(
                version=plan.request.repository_version, reason=exc
            )
        )
        return _publish_full(plan)


class _CannotDerive(Exception):
    """Raised when the base publication cannot represent the target version exactly."""


def _signing_fingerprint(signing_service):
    if signing_service is None:
        return None
    return hashlib.sha256(signing_service.public_key.encode()).hexdigest()


def _has_distribution_trees(repository_version):
    return repository_version.content.filter(pulp_type=DistributionTree.get_pulp_type()).exists()


def _configure_publication(publication, request):
    publication.checksum_type = request.checksum_type
    publication.compression_type = request.compression_type
    publication.layout = request.layout
    publication.repo_config = request.repo_config


@contextmanager
def _publish_workspace():
    """Run a publish attempt in its own directory, so a failed attempt leaves nothing behind."""
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(dir=".") as workdir:
        os.chdir(workdir)
        try:
            yield
        finally:
            os.chdir(cwd)


def _finalize_publication(publication, request, publication_data, repomd_path):
    """Record how the publication was produced and return it serialized."""
    publication.metadata_signing_fingerprint = _signing_fingerprint(
        request.metadata_signing_service
    )
    publication.metadata_fingerprints = _content_fingerprints(
        publication, publication_data.packages, repomd_path
    )
    publication.save()
    return RpmPublicationSerializer(instance=publication, context={"request": None}).data


def _publish_full(plan):
    request = plan.request
    repository = request.repository_version.repository.cast()
    log.info(
        _("Publishing: repository={repo}, version={version}").format(
            repo=repository.name,
            version=request.repository_version.number,
        )
    )
    with _publish_workspace():
        with RpmPublication.create(
            request.repository_version, checkpoint=request.checkpoint
        ) as publication:
            _configure_publication(publication, request)
            publication_data = PublicationData(publication, request.checksum_types)
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
                repomd_path = _generate_repo_metadata(
                    content,
                    publication,
                    request.checksum_types,
                    publication_data.repomdrecords,
                    metadata_signing_service=request.metadata_signing_service,
                    compression_type=request.compression_type,
                    retained_packages=publication_data.packages,
                )
                publish_pb.increment()

                for sub_repo in publication_data.sub_repos:
                    name = sub_repo[0]
                    content = getattr(publication_data, f"{name}_content")
                    extra_repomdrecords = getattr(publication_data, f"{name}_repomdrecords")
                    packages = getattr(publication_data, f"{name}_packages")
                    _generate_repo_metadata(
                        content,
                        publication,
                        request.checksum_types,
                        extra_repomdrecords,
                        name,
                        metadata_signing_service=request.metadata_signing_service,
                        compression_type=request.compression_type,
                        retained_packages=packages,
                    )
                    publish_pb.increment()

            result = _finalize_publication(publication, request, publication_data, repomd_path)
            log.info(_("Publication: {publication} created").format(publication=publication.pk))
            return result


def _generate_repo_metadata(
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
    requested_checksum_type = get_checksum_type(checksum_types)

    if requested_checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
        raise ForbiddenChecksumTypeError(requested_checksum_type, ALLOWED_CHECKSUM_ERROR_MSG)

    if sub_folder:
        cwd = os.path.join(cwd, sub_folder)
        repodata_path = os.path.join(sub_folder, repodata_path)

    # Prepare metadata files
    cr_compression_type, _ = _compression(compression_type)
    total_packages = len(retained_packages)

    repo_pkg_times = _repo_package_times(publication) if RPM_METADATA_USE_REPO_PACKAGE_TIME else {}

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
        for package in (
            Package.objects.filter(pk__in=content).order_by("name", "evr").iterator(chunk_size=200)
        ):
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
            has_modules = False
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

            if has_modules:
                writer.add_repomd_metadata("modules", mod_yml_path, use_compression=False)

        # Process comps - collect model instances and convert to CompsData
        groups = list(PackageGroup.objects.filter(pk__in=content).order_by("id"))
        categories = list(PackageCategory.objects.filter(pk__in=content).order_by("id"))
        environments = list(PackageEnvironment.objects.filter(pk__in=content).order_by("id"))
        package_langpacks = PackageLangpacks.objects.filter(pk__in=content).order_by(
            *PackageLangpacks.natural_key_fields()
        )
        # PackageLangpacks is unique per repo, take first if any exist
        langpacks = package_langpacks.first() if package_langpacks.exists() else None

        has_comps = bool(groups or categories or environments or langpacks)

        if has_comps:
            comps = models_to_comps_data(groups, categories, environments, langpacks)
            with open(comps_xml_path, "w") as f:
                f.write(comps.to_xml())
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
        _sign_repomd(publication, repomd_path, repodata_path, metadata_signing_service)
    else:
        with open(repomd_path, "rb") as repomd_fd:
            PublishedMetadata.create_from_file(
                relative_path=os.path.join(repodata_path, os.path.basename(repomd_path)),
                publication=publication,
                file=File(repomd_fd),
            )

    return repomd_path


def _sign_repomd(publication, repomd_path, repodata_path, signing_service):
    """Sign repomd.xml and publish the signature and public key alongside it."""
    sign_results = signing_service.sign(repomd_path)

    # https://github.com/pulp/pulp_rpm/issues/3526
    signature_file_path = sign_results["signature"]
    if os.stat(signature_file_path).st_size == 0:
        log.error(f"{signature_file_path} is 0 bytes! sign_results: {sign_results}")
        raise MetadataSigningError("Signature file is 0 bytes")

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
            relative_path=os.path.join(repodata_path, os.path.basename(sign_results["signature"])),
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


def _published_path(layout, pkg_filename, checksum):
    """Return the relative path a package is published at."""
    if layout == LAYOUT_TYPES.NESTED_ALPHABETICALLY:
        return os.path.join(PACKAGES_DIRECTORY, pkg_filename[0].lower(), pkg_filename)
    if layout == LAYOUT_TYPES.FLAT:
        return os.path.join(PACKAGES_DIRECTORY, pkg_filename)
    if layout == LAYOUT_TYPES.NESTED_BY_DIGEST:
        # Regardless of checksum type, let's use the first 6 characters of the checksum
        # to create a nested directory structure.
        if len(checksum) < 6:
            raise ChecksumTooShortError(checksum, layout)
        return os.path.join(
            PACKAGES_DIRECTORY,
            pkg_filename[0].lower(),
            "by-digest",
            f"{checksum[:6]}-{pkg_filename}",
        )
    raise UnsupportedLayoutError(layout)


_COMPRESSION = {
    COMPRESSION_TYPES.ZSTD: (cr.ZSTD, ".zst"),
    COMPRESSION_TYPES.NONE: (cr.NO_COMPRESSION, ""),
    COMPRESSION_TYPES.GZ: (cr.GZ, ".gz"),
}


def _compression(compression_type):
    """The createrepo_c compression and metadata file extension for a publication setting."""
    # Gzip is the default option & fallback should the value be something unexpected
    return _COMPRESSION.get(compression_type, _COMPRESSION[COMPRESSION_TYPES.GZ])


def _changed_pulp_types(added_pks, removed_pks):
    """The content types whose membership differs between the base version and the target."""
    delta = added_pks | removed_pks
    if not delta:
        return frozenset()
    return frozenset(
        Content.objects.filter(safe_in("pk", delta)).values_list("pulp_type", flat=True).distinct()
    )


def _nevra_key(name, epoch, version, release, arch):
    return (name, str(int(epoch)) if epoch else "0", version, release, arch)


# Bump when generated metadata changes in a way that older publications cannot represent.
_METADATA_FORMAT = 1


def _digest(items):
    digest = hashlib.sha256()
    for item in sorted(items):
        text = "|".join(str(part) for part in item) if isinstance(item, tuple) else str(item)
        digest.update(text.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _repomd_fingerprint(repomd_path):
    """The set of metadata records in the publication.

    Record checksums and sizes are not usable as a comparison unit: compressed bytes vary
    between identical runs, and a parsed-then-dumped record omits empty optional elements that
    regenerating it from the database emits. The per-type fingerprints cover the content.
    """
    repomd = cr.Repomd()
    cr.xml_parse_repomd(repomd_path, repomd)
    return sorted({record.type for record in repomd.records})


def _content_fingerprints(publication, retained_packages, repomd_path):
    """Describe the client-visible metadata of a publication, per record type.

    Two publications of the same repository version must have equal fingerprints.
    """
    content = publication.repository_version.content
    comps_digests = [
        *PackageGroup.objects.filter(pk__in=content).values_list("digest", flat=True),
        *PackageCategory.objects.filter(pk__in=content).values_list("digest", flat=True),
        *PackageEnvironment.objects.filter(pk__in=content).values_list("digest", flat=True),
        *PackageLangpacks.objects.filter(pk__in=content).values_list("digest", flat=True),
    ]
    module_digests = [
        *Modulemd.objects.filter(pk__in=content).values_list("digest", flat=True),
        *ModulemdDefaults.objects.filter(pk__in=content).values_list("digest", flat=True),
        *(
            f"{obsolete.module_name}:{obsolete.module_stream}:{obsolete.module_context}:"
            f"{obsolete.modified}"
            for obsolete in ModulemdObsolete.objects.filter(pk__in=content)
        ),
    ]
    return {
        "settings": {
            "format": _METADATA_FORMAT,
            "repository_package_time": RPM_METADATA_USE_REPO_PACKAGE_TIME,
        },
        "packages": _digest(
            (info.checksum_type, info.checksum, info.path) for info in retained_packages.values()
        ),
        "updateinfo": _digest(
            UpdateRecord.objects.filter(pk__in=content).values_list("digest", flat=True)
        ),
        "modules": _digest(module_digests),
        "comps": _digest(comps_digests),
        "custom": dict(
            RepoMetadataFile.objects.filter(pk__in=content).values_list("data_type", "checksum")
        ),
        "repomd": _repomd_fingerprint(repomd_path),
    }


def _copy_published_file(published_metadata, destination):
    content_artifact = published_metadata.contentartifact_set.get()
    with open(destination, "wb") as destination_file:
        shutil.copyfileobj(content_artifact.artifact.file.file, destination_file)


def _materialize_base_metadata(base_publication):
    """Copy the base publication's metadata files into the working directory.

    Returns the local path and the open (uncompressed) checksum/size of every record.
    """
    directory = "base-metadata"
    os.makedirs(directory, exist_ok=True)
    repomd_path = os.path.join(directory, "repomd.xml")
    published = {
        metadata.relative_path: metadata
        for metadata in PublishedMetadata.objects.filter(
            publication=base_publication
        ).prefetch_related("contentartifact_set")
    }

    def metadata_for(relative_path):
        try:
            return published[relative_path]
        except KeyError:
            raise PublishedMetadata.DoesNotExist(
                f"{relative_path} missing from publication {base_publication.pk}"
            )

    _copy_published_file(metadata_for(os.path.join(REPODATA_PATH, "repomd.xml")), repomd_path)
    base_repomd = cr.Repomd()
    cr.xml_parse_repomd(repomd_path, base_repomd)

    files = {}
    stats = {}
    for record in base_repomd.records:
        local_path = os.path.join(directory, os.path.basename(record.location_href))
        _copy_published_file(metadata_for(record.location_href), local_path)
        files[record.type] = local_path
        stats[record.type] = (record.checksum_open, record.size_open)
    return files, stats


def _file_stat(path, checksum_type=CHECKSUM_TYPES.SHA256):
    digest = hashlib.new(checksum_type)
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest(), os.path.getsize(path)


def _open_stat(path, checksum_type=CHECKSUM_TYPES.SHA256):
    """Checksum and size of the uncompressed payload, or none for an uncompressed file."""
    compression = cr.detect_compression(path)
    if compression == cr.NO_COMPRESSION:
        return None, None
    uncompressed = tempfile.NamedTemporaryFile(suffix=".xml", dir=".", delete=False).name
    try:
        cr.decompress_file(path, uncompressed, compression)
        return _file_stat(uncompressed, checksum_type)
    finally:
        os.unlink(uncompressed)


def _package_checksum(row, requested_checksum_type, checksum_field):
    """The checksum a package is published with, and its type, validated against the allowlist."""
    if checksum_field and row.get(checksum_field):
        return row[checksum_field], requested_checksum_type
    checksum = row["content__rpm_package__pkgId"]
    checksum_type = row["content__rpm_package__checksum_type"]
    if checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
        raise ForbiddenChecksumTypeError(
            checksum_type,
            _(
                "Package with pkgId {pkgid} as content unit {cid} contains "
                "forbidden checksum type. {error_msg}"
            ).format(
                pkgid=checksum,
                cid=row["content_id"],
                error_msg=ALLOWED_CHECKSUM_ERROR_MSG,
            ),
        )
    return checksum, checksum_type


def _package_details(pks, request):
    """Return {content_id: (PackageInfo, nevra_key)} for the given pks that are packages."""
    requested_checksum_type = request.checksum_type
    checksum_field = f"artifact__{requested_checksum_type}"
    rows = ContentArtifact.objects.filter(
        content__in=Content.objects.filter(safe_in("pk", list(pks))),
        content__pulp_type=Package.get_pulp_type(),
    ).values(
        "pk",
        "content_id",
        "relative_path",
        checksum_field,
        "content__rpm_package__name",
        "content__rpm_package__epoch",
        "content__rpm_package__version",
        "content__rpm_package__release",
        "content__rpm_package__arch",
        "content__rpm_package__pkgId",
        "content__rpm_package__checksum_type",
    )
    details = {}
    for row in rows:
        checksum, checksum_type = _package_checksum(row, requested_checksum_type, checksum_field)
        filename = os.path.basename(row["relative_path"])
        info = PackageInfo(
            caid=row["pk"],
            path=_published_path(request.layout, filename, checksum),
            checksum_type=checksum_type,
            checksum=checksum,
        )
        nevra = _nevra_key(
            row["content__rpm_package__name"],
            row["content__rpm_package__epoch"],
            row["content__rpm_package__version"],
            row["content__rpm_package__release"],
            row["content__rpm_package__arch"],
        )
        details[row["content_id"]] = (info, nevra)
    return details


_MAX_COLLISION_FILENAMES = 1000


def _target_package_keys(version, delta_pks, delta_keys):
    """Keys of the packages remaining in the version that could collide with the delta.

    A NEVRA collision requires the same name, so only packages sharing a delta name are
    considered for it. Filename collisions do not: packages with different names can be
    published at the same path, and a full publish keeps only one of them.
    """
    names = {nevra[0] for nevra, _ in delta_keys}
    delta_filenames = {filename for _, filename in delta_keys}
    if not names and not delta_filenames:
        return set(), set()
    if len(delta_filenames) > _MAX_COLLISION_FILENAMES:
        raise _CannotDerive("the delta is too large to validate path collisions")
    candidate_filter = Q(content__rpm_package__name__in=names)
    for filename in delta_filenames:
        candidate_filter |= Q(relative_path=filename) | Q(relative_path__endswith=f"/{filename}")
    delta_content = Content.objects.filter(safe_in("pk", delta_pks))
    rows = list(
        ContentArtifact.objects.filter(
            content__in=version.content,
            content__pulp_type=Package.get_pulp_type(),
        )
        .exclude(content_id__in=delta_content)
        .filter(candidate_filter)
        .values(
            "relative_path",
            "content__rpm_package__name",
            "content__rpm_package__epoch",
            "content__rpm_package__version",
            "content__rpm_package__release",
            "content__rpm_package__arch",
        )
    )
    nevras = {
        _nevra_key(
            row["content__rpm_package__name"],
            row["content__rpm_package__epoch"],
            row["content__rpm_package__version"],
            row["content__rpm_package__release"],
            row["content__rpm_package__arch"],
        )
        for row in rows
    }
    retained_filenames = {os.path.basename(row["relative_path"]) for row in rows}
    return nevras, retained_filenames


def _packages_to_add(plan, retained):
    added = [pk for pk in plan.delta.added_pks if pk in retained]
    if not added:
        return []
    added_content = Content.objects.filter(safe_in("pk", added))
    return list(Package.objects.filter(pk__in=added_content).order_by("name", "evr"))


_UNPUBLISHABLE_TYPES = (
    RepoMetadataFile.get_pulp_type(),
    Modulemd.get_pulp_type(),
    ModulemdDefaults.get_pulp_type(),
    Package.get_pulp_type(),
    # A publication's own metadata files are published by create_from_file, which writes their
    # PublishedArtifact rows itself.
    PublishedMetadata.get_pulp_type(),
)


def _base_package_checksums(primary_path):
    """Map a base publication's package path to its published checksum and checksum type."""
    checksums = {}

    def collect(package):
        checksums[package.location_href] = (package.pkgId, package.checksum_type)
        return 0

    cr.xml_parse_primary(primary_path, pkgcb=collect)
    return checksums


def _populate_derived(publication, publication_data, plan, base_files):
    """Populate a derived publication by inheriting the base rows for retained content.

    The base publication already made the checksum, path and collision-winner decisions for
    everything it published; only the packages the delta adds need new decisions.
    """
    request = plan.request
    base = plan.base_publication
    removed = plan.delta.removed_pks
    publication_data.repomdrecords = publication_data.prepare_metadata_files(
        request.repository_version.content
    )

    rows = []

    def add_row(caid, path):
        rows.append(
            PublishedArtifact(publication=publication, content_artifact_id=caid, relative_path=path)
        )

    packages = {}
    if "primary" not in base_files:
        raise _CannotDerive("base publication has no primary record")
    base_checksums = _base_package_checksums(base_files["primary"])
    package_type = Package.get_pulp_type()
    base_rows = PublishedArtifact.objects.filter(publication=base).values_list(
        "content_artifact_id",
        "relative_path",
        "content_artifact__content_id",
        "content_artifact__content__pulp_type",
    )
    for caid, path, cid, pulp_type in base_rows:
        if cid in removed or path in ("treeinfo", ".treeinfo"):
            continue
        if pulp_type == package_type:
            try:
                checksum, checksum_type = base_checksums[path]
            except KeyError:
                raise _CannotDerive(f"package {path} missing from the base primary metadata")
            packages[cid] = PackageInfo(
                caid=caid, path=path, checksum_type=checksum_type, checksum=checksum
            )
        elif pulp_type in _UNPUBLISHABLE_TYPES:
            continue
        add_row(caid, path)

    # A deletion after this point leaves the inherited rows valid (they reference the shared
    # content artifacts), but one that raced the query above would silently drop content.
    if not RpmPublication.objects.filter(pk=base.pk).exists():
        raise _CannotDerive("base publication was deleted while deriving")

    added = [pk for pk in plan.delta.added_pks if pk not in packages]
    for cid, (info, _nevra) in _package_details(added, request).items():
        packages[cid] = info
        add_row(info.caid, info.path)

    added_content = Content.objects.filter(safe_in("pk", list(plan.delta.added_pks)))
    added_artifacts = (
        ContentArtifact.objects.filter(content__in=added_content)
        .exclude(content__pulp_type__in=_UNPUBLISHABLE_TYPES)
        .exclude(relative_path__in=["treeinfo", ".treeinfo"])
        .values_list("pk", "relative_path")
    )
    for caid, path in added_artifacts:
        add_row(caid, path)

    PublishedArtifact.objects.bulk_create(rows, batch_size=2000)
    publication_data.packages = packages


def _validate_package_delta(plan):
    """Refuse to derive when the published winner of a NEVRA or a filename could change."""
    delta_pks = plan.delta.added_pks | plan.delta.removed_pks
    delta_keys = {
        (nevra, os.path.basename(info.path))
        for info, nevra in _package_details(delta_pks, plan.request).values()
    }
    retained_nevras, retained_filenames = _target_package_keys(
        plan.request.repository_version, delta_pks, delta_keys
    )
    for nevra, filename in delta_keys:
        if nevra in retained_nevras or filename in retained_filenames:
            raise _CannotDerive(f"collision key overlap on {nevra} / {filename}")
    if len({nevra for nevra, _ in delta_keys}) != len(delta_keys):
        raise _CannotDerive("duplicate NEVRA in delta")
    if len({filename for _, filename in delta_keys}) != len(delta_keys):
        raise _CannotDerive("duplicate filename in delta")


def _package_times(repository, version_number):
    """When each unit currently in the version entered the repository."""
    repo_content = (
        RepositoryContent.objects.filter(
            repository=repository,
            version_added__number__lte=version_number,
        )
        .exclude(version_removed__number__lte=version_number)
        .values_list("content", "pulp_created")
    )
    return {pk: created.timestamp() for pk, created in repo_content}


def _repo_package_times(publication):
    return _package_times(publication.repository, publication.repository_version.number)


def _package_block_checksum(block):
    """Return the pkgId of a serialized <package> block."""
    if 'pkgid="YES"' in block:
        start = block.index('pkgid="YES">') + len('pkgid="YES">')
        return block[start : block.index("</checksum>", start)]
    start = block.index('pkgid="') + len('pkgid="')
    return block[start : block.index('"', start)]


def _splice_stream(source, target, retained_checksums, added_chunks, expected_count, checksum_type):
    """Copy retained <package> blocks verbatim, append delta chunks, fix the package count.

    Returns the checksum and size of the uncompressed payload written. ``checksum_type`` is None
    for an uncompressed record, which gets no open-checksum.
    """
    digest = hashlib.new(checksum_type) if checksum_type else None
    size = 0

    def emit(text):
        nonlocal size
        target.write(text)
        data = text.encode("utf-8")
        if digest:
            digest.update(data)
        size += len(data)

    header_done = False
    first_line = None
    root = None
    for line in source:
        first_line = first_line or line
        if line.lstrip().startswith(("<metadata", "<filelists", "<otherdata")):
            root = re.match(r"\s*<(\w+)", line).group(1)
            line = re.sub(r'packages="\d+"', f'packages="{expected_count}"', line)
            emit(line)
            header_done = True
            break
        if "<package" in line:
            break
        emit(line)
    if not header_done:
        raise _CannotDerive(f"unexpected metadata header: {first_line[:100]!r}")

    written = 0
    block = []
    for line in source:
        if line.strip().startswith(f"</{root}"):
            break
        if not block and not line.startswith("<package "):
            continue
        block.append(line)
        if "</package>" in block[-1]:
            text = "".join(block)
            block = []
            try:
                checksum = _package_block_checksum(text)
            except ValueError:
                raise _CannotDerive("unrecognized package block")
            if checksum in retained_checksums:
                emit(text)
                written += 1

    for chunk in added_chunks:
        emit(chunk)
        if not chunk.endswith("\n"):
            emit("\n")
        written += 1
    emit(f"</{root}>\n")

    if written != expected_count:
        raise _CannotDerive(f"wrote {written} of {expected_count} package entries")
    return (digest.hexdigest() if digest else None), size


def _package_chunks(added_packages, retained_info, repo_pkg_times, dump):
    """Serialize the packages the delta adds, with the published checksum and path."""
    chunks = []
    for package in added_packages:
        info = retained_info[package.pk]
        cr_package = package.to_createrepo_c()
        cr_package.checksum_type = info.checksum_type
        cr_package.pkgId = info.checksum
        cr_package.location_href = info.path
        if repo_pkg_times:
            cr_package.time_file = repo_pkg_times[package.pk]
        chunks.append(dump(cr_package))
    return chunks


def _splice_packages(
    base_path,
    output_path,
    retained_checksums,
    added_chunks,
    expected_count,
    cr_compression,
    checksum_type,
):
    """Write the spliced package metadata and return its open checksum and size."""
    open_checksum_type = None if cr_compression == cr.NO_COMPRESSION else checksum_type

    def splice(source, target):
        return _splice_stream(
            source,
            target,
            retained_checksums,
            added_chunks,
            expected_count,
            open_checksum_type,
        )

    if cr_compression == cr.ZSTD:
        uncompressed = tempfile.NamedTemporaryFile("w", suffix=".xml", dir=".", delete=False).name
        spliced = tempfile.NamedTemporaryFile("w", suffix=".xml", dir=".", delete=False).name
        try:
            cr.decompress_file(base_path, uncompressed, cr.ZSTD)
            with (
                open(uncompressed, encoding="utf-8") as source,
                open(spliced, "w", encoding="utf-8") as target,
            ):
                stat = splice(source, target)
            cr.compress_file(spliced, output_path, cr.ZSTD)
            return stat
        finally:
            for path in (uncompressed, spliced):
                if os.path.exists(path):
                    os.unlink(path)

    try:
        if cr_compression == cr.GZ:
            # compresslevel matches createrepo_c's zlib default; gzip.open defaults to 9 and
            # spends several times longer on the large files.
            with (
                gzip.open(base_path, "rt", encoding="utf-8") as source,
                gzip.open(output_path, "wt", encoding="utf-8", compresslevel=6) as target,
            ):
                return splice(source, target)

        with (
            open(base_path, encoding="utf-8") as source,
            open(output_path, "w", encoding="utf-8") as target,
        ):
            return splice(source, target)
    except _CannotDerive as exc:
        raise _CannotDerive(f"{os.path.basename(base_path)}: {exc}")


def _write_compressed(text, path, cr_compression):
    if cr_compression == cr.NO_COMPRESSION:
        with open(path, "w", encoding="utf-8") as output:
            output.write(text)
        return
    # createrepo_c detects the compression of the source from its extension.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".xml", dir=".", delete=False, encoding="utf-8"
    ) as output:
        output.write(text)
        uncompressed = output.name
    try:
        cr.compress_file(uncompressed, path, cr_compression)
    finally:
        os.unlink(uncompressed)


def _reuse_base_record(record, filename, base_files, base_stats):
    """Copy the base publication's unchanged record under a neutral name."""
    if record not in base_files:
        return None
    path = os.path.join(REPODATA_PATH, filename)
    shutil.copyfile(base_files[record], path)
    return path, *base_stats[record]


def _records_unchanged(changed_types, models):
    return not any(model.get_pulp_type() in changed_types for model in models)


def _updateinfo_file(
    plan, base_files, base_stats, cr_compression, extension, checksum_type, changed_types
):
    version = plan.request.repository_version

    if UpdateRecord.get_pulp_type() not in changed_types:
        return _reuse_base_record(
            "updateinfo", f"updateinfo.xml{extension}", base_files, base_stats
        )

    if (
        UpdateRecord.objects.filter(pk__in=version.content)
        .values("id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .exists()
    ):
        raise _CannotDerive("duplicate advisory ids in the target version")

    target_ids = set(
        UpdateRecord.objects.filter(pk__in=version.content).values_list("id", flat=True)
    )
    records = {}
    if "updateinfo" in base_files:
        base_updates = cr.UpdateInfo(base_files["updateinfo"]).updates
        if len({record.id for record in base_updates}) != len(base_updates):
            raise _CannotDerive("base updateinfo has duplicate advisory ids")
        for record in base_updates:
            if record.id in target_ids:
                records[record.id] = record
    added_content = Content.objects.filter(safe_in("pk", list(plan.delta.added_pks)))
    for advisory in UpdateRecord.objects.filter(pk__in=added_content):
        records[advisory.id] = advisory.to_createrepo_c()
    if not records:
        return None

    updateinfo = cr.UpdateInfo()
    for record in records.values():
        updateinfo.append(record)
    text = updateinfo.xml_dump()
    path = os.path.join(REPODATA_PATH, f"updateinfo.xml{extension}")
    _write_compressed(text, path, cr_compression)
    encoded = text.encode("utf-8")
    if cr_compression == cr.NO_COMPRESSION:
        return path, None, None
    return path, hashlib.new(checksum_type, encoded).hexdigest(), len(encoded)


def _modules_file(plan, base_files, base_stats, changed_types):
    version = plan.request.repository_version
    models = (Modulemd, ModulemdDefaults, ModulemdObsolete)

    if _records_unchanged(changed_types, models):
        return _reuse_base_record("modules", "modules.yaml", base_files, base_stats)

    content = version.content
    path = os.path.join(REPODATA_PATH, "modules.yaml")
    has_modules = False
    with open(path, "wb") as mod_yml:
        for model in models:
            entries = model.objects.filter(pk__in=content).order_by(*model.natural_key_fields())
            for entry in entries:
                mod_yml.write(entry.snippet.encode())
                mod_yml.write(b"\n")
                has_modules = True
    if not has_modules:
        os.unlink(path)
        return None
    # createrepo_c records no open-checksum for this uncompressed extra metadata file.
    return path, None, None


def _comps_file(plan, base_files, base_stats, changed_types):
    version = plan.request.repository_version
    models = (PackageGroup, PackageCategory, PackageEnvironment, PackageLangpacks)

    if _records_unchanged(changed_types, models):
        return _reuse_base_record("group", "comps.xml", base_files, base_stats)

    content = version.content
    groups = list(PackageGroup.objects.filter(pk__in=content).order_by("id"))
    categories = list(PackageCategory.objects.filter(pk__in=content).order_by("id"))
    environments = list(PackageEnvironment.objects.filter(pk__in=content).order_by("id"))
    langpacks = (
        PackageLangpacks.objects.filter(pk__in=content)
        .order_by(*PackageLangpacks.natural_key_fields())
        .first()
    )

    if not (groups or categories or environments or langpacks):
        return None

    comps = models_to_comps_data(groups, categories, environments, langpacks)
    path = os.path.join(REPODATA_PATH, "comps.xml")
    with open(path, "w", encoding="utf-8") as comps_file:
        comps_file.write(comps.to_xml())
    # createrepo_c records no open-checksum for this uncompressed extra metadata file.
    return path, None, None


def _write_repomd(publication, records, empty=False):
    repomd = cr.Repomd()
    if empty:
        # If the repository is empty, use a revision of 0
        # See: https://pulp.plan.io/issues/9402
        repomd.revision = "0"
    finalized = []
    for record_type, path, open_checksum, open_size in records:
        checksum, size = _file_stat(path, publication.checksum_type)
        directory, name = os.path.split(path)
        final_path = os.path.join(directory, f"{checksum}-{name}")
        if final_path != path:
            os.replace(path, final_path)
        record = cr.RepomdRecord(record_type, final_path)
        record.checksum_type = publication.checksum_type
        record.checksum = checksum
        record.size = size
        if open_checksum:
            record.checksum_open_type = publication.checksum_type
            record.checksum_open = open_checksum
            record.size_open = open_size
        record.timestamp = int(time.time())
        repomd.set_record(record)
        finalized.append((record_type, final_path))
    repomd_path = os.path.join(REPODATA_PATH, "repomd.xml")
    with open(repomd_path, "w") as repomd_file:
        repomd_file.write(repomd.xml_dump())
    return repomd_path, finalized


def _publish_metadata_file(publication, path):
    with open(path, "rb") as metadata_file:
        PublishedMetadata.create_from_file(
            relative_path=os.path.relpath(path),
            publication=publication,
            file=File(metadata_file),
        )


def _custom_metadata_records(publication_data, cr_compression, extension, checksum_type):
    """Compress the custom metadata files the same way RepositoryWriter does."""
    records = []
    for data_type, path in publication_data.repomdrecords:
        source_compression = cr.detect_compression(path)
        if source_compression != cr.NO_COMPRESSION:
            if source_compression != cr_compression:
                raise _CannotDerive(
                    f"custom metadata {data_type} is pre-compressed with a different type"
                )
            destination = os.path.join(REPODATA_PATH, os.path.basename(path))
            shutil.copyfile(path, destination)
            stat = _open_stat(destination, checksum_type)
        elif cr_compression == cr.NO_COMPRESSION:
            destination = os.path.join(REPODATA_PATH, os.path.basename(path))
            shutil.copyfile(path, destination)
            stat = (None, None)
        else:
            destination = os.path.join(REPODATA_PATH, os.path.basename(path) + extension)
            cr.compress_file(path, destination, cr_compression)
            stat = _file_stat(path, checksum_type)
        records.append((data_type, destination, *stat))
    return records


def _generate_derived_metadata(publication, publication_data, plan, base_files, base_stats):
    """Build the publication's metadata from its base publication plus the version delta."""
    request = plan.request
    version = request.repository_version
    cr_compression, extension = _compression(request.compression_type)
    checksum_type = publication.checksum_type
    changed_types = plan.delta.changed_types

    content_checksum_type = get_checksum_type(request.checksum_types)
    if content_checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
        raise ForbiddenChecksumTypeError(content_checksum_type, ALLOWED_CHECKSUM_ERROR_MSG)

    os.makedirs(REPODATA_PATH, exist_ok=True)
    records = []

    repo_pkg_times = _repo_package_times(publication) if RPM_METADATA_USE_REPO_PACKAGE_TIME else {}
    if RPM_METADATA_USE_REPO_PACKAGE_TIME:
        base_times = _package_times(
            plan.base_publication.repository, plan.base_publication.repository_version.number
        )
        common = base_times.keys() & repo_pkg_times.keys()
        if any(base_times[pk] != repo_pkg_times[pk] for pk in common):
            # Retained entries would keep the base's <time file> for a package that was
            # re-added at a different time.
            raise _CannotDerive("repository package times changed")

    packages_unchanged = Package.get_pulp_type() not in changed_types
    if packages_unchanged:
        for name in ("primary", "filelists", "other"):
            path = os.path.join(REPODATA_PATH, f"{name}.xml{extension}")
            shutil.copyfile(base_files[name], path)
            records.append((name, path, *base_stats[name]))
    else:
        for name in ("primary", "filelists", "other"):
            if name not in base_files:
                raise _CannotDerive(f"base publication has no {name} record")
        added_packages = _packages_to_add(plan, publication_data.packages)
        _validate_package_delta(plan)
        retained_checksums = {info.checksum for info in publication_data.packages.values()}
        for name, dump in (
            ("primary", cr.xml_dump_primary),
            ("filelists", cr.xml_dump_filelists),
            ("other", cr.xml_dump_other),
        ):
            path = os.path.join(REPODATA_PATH, f"{name}.xml{extension}")
            open_stat = _splice_packages(
                base_files[name],
                path,
                retained_checksums,
                _package_chunks(added_packages, publication_data.packages, repo_pkg_times, dump),
                len(publication_data.packages),
                cr_compression,
                checksum_type,
            )
            records.append((name, path, *open_stat))

    updateinfo_path = _updateinfo_file(
        plan, base_files, base_stats, cr_compression, extension, checksum_type, changed_types
    )
    if updateinfo_path:
        records.append(("updateinfo", *updateinfo_path))

    modules_path = _modules_file(plan, base_files, base_stats, changed_types)
    if modules_path:
        records.append(("modules", *modules_path))

    comps_path = _comps_file(plan, base_files, base_stats, changed_types)
    if comps_path:
        records.append(("group", *comps_path))

    records.extend(
        _custom_metadata_records(publication_data, cr_compression, extension, checksum_type)
    )

    repomd_path, finalized = _write_repomd(publication, records, empty=not version.content.exists())
    for record_type, path in finalized:
        _publish_metadata_file(publication, path)
    if request.metadata_signing_service:
        _sign_repomd(publication, repomd_path, REPODATA_PATH, request.metadata_signing_service)
    else:
        _publish_metadata_file(publication, repomd_path)
    return repomd_path


def _publish_derived(plan):
    request = plan.request
    repository = request.repository_version.repository.cast()
    log.info(
        _("Deriving publication: repository={repo}, version={version}, base={base}").format(
            repo=repository.name,
            version=request.repository_version.number,
            base=plan.base_publication.pk,
        )
    )
    with _publish_workspace():
        with RpmPublication.create(
            request.repository_version, checkpoint=request.checkpoint
        ) as publication:
            _configure_publication(publication, request)
            publication.base_publication = plan.base_publication
            publication.save()

            publication_data = PublicationData(publication, request.checksum_types)
            base_files, base_stats = _materialize_base_metadata(plan.base_publication)
            _populate_derived(publication, publication_data, plan, base_files)

            repomd_path = _generate_derived_metadata(
                publication, publication_data, plan, base_files, base_stats
            )

            result = _finalize_publication(publication, request, publication_data, repomd_path)
            log.info(_("Publication: {publication} derived").format(publication=publication.pk))
            return result
