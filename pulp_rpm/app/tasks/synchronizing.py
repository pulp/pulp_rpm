import asyncio
import collections
import json
import logging
import os
import re
import tempfile

from collections import defaultdict
from gettext import gettext as _  # noqa:F401

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.db import transaction
from django.db.models import Q

from aiohttp.client_exceptions import ClientResponseError
from aiohttp.web_exceptions import HTTPNotFound

import createrepo_c as cr
import libcomps

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    ProgressReport,
    Remote,
    PublishedArtifact,
    PublishedMetadata,
)
from pulpcore.plugin.stages import (
    ArtifactDownloader,
    ArtifactSaver,
    ContentSaver,
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    RemoteArtifactSaver,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents,
)

from pulp_rpm.app.advisory import hash_update_record
from pulp_rpm.app.constants import (
    CHECKSUM_TYPES,
    COMPS_REPODATA,
    DIST_TREE_MAIN_REPO_PATH,
    MODULAR_REPODATA,
    PACKAGE_DB_REPODATA,
    PACKAGE_REPODATA,
    PULP_MODULE_ATTR,
    PULP_MODULEDEFAULTS_ATTR,
    SYNC_POLICIES,
    UPDATE_REPODATA,
)
from pulp_rpm.app.models import (
    Addon,
    Checksum,
    DistributionTree,
    Image,
    Variant,
    Modulemd,
    ModulemdDefaults,
    Package,
    RepoMetadataFile,
    PackageGroup,
    PackageCategory,
    PackageEnvironment,
    PackageLangpacks,
    RpmPublication,
    RpmRemote,
    RpmRepository,
    UlnRemote,
    UpdateCollection,
    UpdateCollectionPackage,
    UpdateRecord,
    UpdateReference,
)
from pulp_rpm.app.modulemd import (
    parse_defaults,
    parse_modulemd,
)
from pulp_rpm.app.kickstart.treeinfo import PulpTreeInfo, TreeinfoData

from pulp_rpm.app.comps import strdict_to_dict, dict_digest
from pulp_rpm.app.shared_utils import is_previous_version, get_sha256, urlpath_sanitize
from pulp_rpm.app.metadata_parsing import MetadataParser

import gi

gi.require_version("Modulemd", "2.0")
from gi.repository import Modulemd as mmdlib  # noqa: E402

log = logging.getLogger(__name__)


# TODO: https://pulp.plan.io/issues/8687
# A global dictionary for storing data about the remote's metadata files, used for mirroring
# Indexed by repository.pk due to sub-repos.
metadata_files_for_mirroring = collections.defaultdict(dict)
# A global dictionary for storing data mapping pkgid to location_href for all packages, used
# for mirroring. Indexed by repository.pk due to sub-repos.
pkgid_to_location_href = collections.defaultdict(dict)


MIRROR_INCOMPATIBLE_REPO_ERR_MSG = (
    "This repository uses features which are incompatible with 'mirror' sync. "
    "Please sync without mirroring enabled."
)


def store_metadata_for_mirroring(repo, md_path, relative_path):
    """Used to store data about the downloaded metadata for mirror-publishing after the sync.

    Args:
        repo: Which repository the metadata is associated with
        md_path: The path to the metadata file
        relative_path: The relative path to the metadata file within the repository
    """
    global metadata_files_for_mirroring
    metadata_files_for_mirroring[str(repo.pk)][relative_path] = md_path


def store_package_for_mirroring(repo, pkgid, location_href):
    """Used to store data about the packages for mirror-publishing after the sync.

    Args:
        repo: Which repository the metadata is associated with
        pkgid: The checksum of the package
        location_href: The relative path to the package within the repository
    """
    global pkgid_to_location_href
    pkgid_to_location_href[str(repo.pk)][pkgid] = location_href


def add_metadata_to_publication(publication, version, prefix=""):
    """Create a mirrored publication for the given repository version.

    Uses the `metadata_files` global data.

    Args:
        publication: The publication to add downloaded repo metadata to
        version: The repository version the repo corresponds to
    Kwargs:
        prefix: Subdirectory underneath the root repository (if a sub-repo)
    """
    repo_metadata_files = metadata_files_for_mirroring[str(version.repository.pk)]

    has_repomd_signature = "repodata/repomd.xml.asc" in repo_metadata_files.keys()
    has_sqlite = any([".sqlite" in href for href in repo_metadata_files.keys()])

    publication.package_checksum_type = CHECKSUM_TYPES.UNKNOWN
    publication.metadata_checksum_type = CHECKSUM_TYPES.UNKNOWN
    publication.gpgcheck = 0
    publication.repo_gpgcheck = has_repomd_signature
    publication.sqlite_metadata = has_sqlite

    for (relative_path, metadata_file_path) in repo_metadata_files.items():
        PublishedMetadata.create_from_file(
            file=File(open(metadata_file_path, "rb")),
            relative_path=os.path.join(prefix, relative_path),
            publication=publication,
        )

    published_artifacts = []

    # Handle packages
    pkg_data = (
        ContentArtifact.objects.filter(
            content__in=version.content, content__pulp_type=Package.get_pulp_type()
        )
        .select_related("content__rpm_package")
        .only("pk", "artifact", "content", "content__rpm_package__pkgId")
    )
    for ca in pkg_data.iterator():
        relative_path = pkgid_to_location_href[str(version.repository.pk)][
            ca.content.rpm_package.pkgId
        ]
        pa = PublishedArtifact(
            content_artifact=ca,
            relative_path=os.path.join(prefix, relative_path),
            publication=publication,
        )
        published_artifacts.append(pa)

    # Handle everything else
    # TODO: this code is copied directly from publication, we should deduplicate it later
    # (if possible)
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
        ContentArtifact.objects.filter(content__in=version.content)
        .exclude(unpublishable_types)
        .exclude(is_treeinfo)
    )

    for content_artifact in contentartifact_qs.values("pk", "relative_path").iterator():
        published_artifacts.append(
            PublishedArtifact(
                relative_path=content_artifact["relative_path"],
                publication=publication,
                content_artifact_id=content_artifact["pk"],
            )
        )

    PublishedArtifact.objects.bulk_create(published_artifacts)


def get_repomd_file(remote, url):
    """
    Check if repodata exists.

    Args:
        remote (RpmRemote or UlnRemote): An RpmRemote or UlnRemote to download with.
        url (str): A remote repository URL

    Returns:
        pulpcore.plugin.download.DownloadResult: downloaded repomd.xml

    """
    # URLs, esp mirrorlist URLs, can come into this method with parameters attached.
    # This causes the urlpath_sanitize() below to return something like
    # "http://path?param&param/repodata/repomd.xml", which is **not** an expected/useful response.
    # Make sure we're only looking for the repomd.xml file, no matter what weirdness comes
    # in. See https://pulp.plan.io/issues/8981 for more details.
    url = url.split("?")[0]
    downloader = remote.get_downloader(url=urlpath_sanitize(url, "repodata/repomd.xml"))
    return downloader.fetch()


def fetch_mirror(remote):
    """Fetch the first valid mirror from a list of all available mirrors from a mirror list feed.

    URLs which are commented out or have any punctuations in front of them are being ignored.
    """
    downloader = remote.get_downloader(url=remote.url.rstrip("/"), urlencode=False)
    result = downloader.fetch()

    url_pattern = re.compile(r"(^|^[\w\s=]+\s)((http(s)?)://.*)")
    with open(result.path) as mirror_list_file:
        for mirror in mirror_list_file:
            match = re.match(url_pattern, mirror)
            if not match:
                continue

            mirror_url = match.group(2)
            try:
                get_repomd_file(remote, mirror_url)
                # just check if the metadata exists
                return mirror_url
            except Exception as exc:
                log.warning(
                    "Url '{}' from mirrorlist was tried and failed with error: {}".format(
                        mirror_url, exc
                    )
                )
                continue

    return None


def fetch_remote_url(remote):
    """Fetch a single remote from which can be content synced."""

    def normalize_url(url):
        return url.rstrip("/") + "/"

    try:
        normalized_remote_url = normalize_url(remote.url)
        get_repomd_file(remote, normalized_remote_url)
        # just check if the metadata exists
        return normalized_remote_url
    except ClientResponseError as exc:
        log.info(
            _("Attempting to resolve a true url from potential mirrolist url '{}'").format(
                remote.url
            )
        )
        remote_url = fetch_mirror(remote)
        if remote_url:
            log.info(
                _("Using url '{}' from mirrorlist in place of the provided url {}").format(
                    remote_url, remote.url
                )
            )
            return normalize_url(remote_url)

        if exc.status == 404:
            raise ValueError(_("An invalid remote URL was provided: {}").format(remote.url))

        raise exc


def should_optimize_sync(sync_details, last_sync_details):
    """
    Check whether the sync should be optimized by comparing its parameters with the previous sync.

    Args:
        sync_details (dict): A collection of details about the current sync configuration.
        last_sync_details (dict): A collection of details about the previous sync configuration.

    Returns:
        bool: True, if sync is optimized; False, otherwise.

    """
    might_download_content = (
        last_sync_details.get("download_policy") != "immediate"
        and sync_details["download_policy"] == "immediate"
    )
    might_create_publication = (
        last_sync_details.get("sync_policy") != SYNC_POLICIES.MIRROR_COMPLETE
        and sync_details["sync_policy"] == SYNC_POLICIES.MIRROR_COMPLETE
    )
    if might_download_content or might_create_publication:
        return False

    url_has_changed = last_sync_details.get("url") != sync_details["url"]
    repository_has_been_modified = (
        last_sync_details.get("most_recent_version") != sync_details["most_recent_version"]
    )
    if url_has_changed or repository_has_been_modified:
        return False

    old_revision = is_previous_version(sync_details["revision"], last_sync_details.get("revision"))
    same_revision = last_sync_details.get("revision") == sync_details["revision"]
    same_repomd_checksum = (
        last_sync_details.get("repomd_checksum") == sync_details["repomd_checksum"]
    )
    if not old_revision or not (same_revision and same_repomd_checksum):
        return False

    return True


def synchronize(remote_pk, repository_pk, sync_policy, skip_types, optimize):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    If sync_policy=mirror_complete, a publication will be created with a copy of the original
    metadata. This comes with some limitations, namely:

    * SRPMs and other types listed in "skip_types" will *not* be skipped.
    * If the repository uses the xml:base / location_base feature, then the sync will fail.
      This feature is incompatible with the intentions of most Pulp users, because the metadata
      will tell clients to look for files at some source outside of the Pulp-hosted repo.
    * If the repository uses Delta RPMs, the sync will fail, because Pulp does not support them,
      and cannot change the repository metadata to remove them.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        sync_policy (str): How to perform the sync.
        skip_types (list): List of content to skip.
        optimize(bool): Optimize mode.

    Raises:
        ValueError: If the remote does not specify a url to sync.

    """
    try:
        remote = RpmRemote.objects.get(pk=remote_pk)
    except ObjectDoesNotExist:
        remote = UlnRemote.objects.get(pk=remote_pk)
    repository = RpmRepository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A remote must have a url specified to synchronize."))

    log.info(_("Synchronizing: repository={r} remote={p}").format(r=repository.name, p=remote.name))

    deferred_download = remote.policy != Remote.IMMEDIATE  # Interpret download policy

    def get_treeinfo_data(remote, remote_url):
        """Get Treeinfo data from remote."""
        treeinfo_serialized = {}
        namespaces = [".treeinfo", "treeinfo"]
        for namespace in namespaces:
            downloader = remote.get_downloader(
                url=urlpath_sanitize(remote_url, namespace),
                silence_errors_for_response_status_codes={403, 404},
            )

            try:
                result = downloader.fetch()
            except FileNotFoundError:
                continue

            treeinfo = PulpTreeInfo()
            treeinfo.load(f=result.path)
            sha256 = result.artifact_attributes["sha256"]
            treeinfo_data = TreeinfoData(treeinfo.parsed_sections())

            # get the data we need before changing the original
            treeinfo_serialized = treeinfo_data.to_dict(hash=sha256, filename=namespace)

            # rewrite the treeinfo file such that the variant repository and package location
            # is a relative subtree
            treeinfo.rewrite_subrepo_paths(treeinfo_data)

            # TODO: better way to do this?
            main_variant = treeinfo.original_parser._sections.get("general", {}).get(
                "variant", None
            )
            treeinfo_file = tempfile.NamedTemporaryFile(dir=".", delete=False)
            treeinfo.dump(treeinfo_file.name, main_variant=main_variant)
            store_metadata_for_mirroring(repository, treeinfo_file.name, namespace)
            break

        return treeinfo_serialized

    def get_sync_details(remote, url, sync_policy, version):
        with tempfile.TemporaryDirectory("."):
            result = get_repomd_file(remote, url)
            repomd_path = result.path
            repomd = cr.Repomd(repomd_path)
            repomd_checksum = get_sha256(repomd_path)

        return {
            "url": remote.url,  # use the original remote url so that mirrorlists are optimizable
            "download_policy": remote.policy,
            "sync_policy": sync_policy,
            "most_recent_version": version.number,
            "revision": repomd.revision,
            "repomd_checksum": repomd_checksum,
        }

    mirror = sync_policy.startswith("mirror")
    mirror_metadata = sync_policy == SYNC_POLICIES.MIRROR_COMPLETE

    repo_sync_config = {}
    # this is the "directory" of the repo within the target repo location - for the primary
    # repo, they are the same
    PRIMARY_REPO = ""

    def is_subrepo(directory):
        return directory != PRIMARY_REPO

    with tempfile.TemporaryDirectory("."):
        remote_url = fetch_remote_url(remote)
        sync_details = get_sync_details(
            remote, remote_url, sync_policy, repository.latest_version()
        )

        repo_sync_config[PRIMARY_REPO] = {
            "should_skip": should_optimize_sync(sync_details, repository.last_sync_details),
            "sync_details": sync_details,
            "url": remote_url,
            "repo": repository,
        }

        treeinfo = get_treeinfo_data(remote, remote_url)

        if treeinfo:
            treeinfo["repositories"] = {}
            for repodata in set(treeinfo["download"]["repodatas"]):
                if repodata == DIST_TREE_MAIN_REPO_PATH:
                    treeinfo["repositories"].update({repodata: None})
                    continue
                name = f"{repodata}-{treeinfo['hash']}"
                sub_repo, created = RpmRepository.objects.get_or_create(name=name, user_hidden=True)
                if created:
                    sub_repo.save()
                directory = treeinfo["repo_map"][repodata]
                treeinfo["repositories"].update({directory: str(sub_repo.pk)})
                path = f"{repodata}/"
                new_url = urlpath_sanitize(remote_url, path)

                try:
                    subrepo_sync_details = get_sync_details(
                        remote, new_url, sync_policy, sub_repo.latest_version()
                    )
                except ClientResponseError as exc:
                    if is_subrepo(directory) and exc.status == 404:
                        log.warning("Unable to sync sub-repo '{}' from treeinfo.".format(directory))
                        continue
                    raise exc

                repo_sync_config[directory] = {
                    "should_skip": should_optimize_sync(
                        subrepo_sync_details, sub_repo.last_sync_details
                    ),
                    "sync_details": subrepo_sync_details,
                    "url": new_url,
                    "repo": sub_repo,
                }

        # If all repos are exactly the same, we should skip all further processing, even in
        # metadata-mirror mode
        if optimize and all([config["should_skip"] for config in repo_sync_config.values()]):
            with ProgressReport(
                message="Skipping Sync (no change from previous sync)", code="sync.was_skipped"
            ) as pb:
                pb.done = len(repo_sync_config)
                pb.total = len(repo_sync_config)
            return

        skipped_syncs = 0
        repo_sync_results = {}

        # If some repos need to be synced and others do not, we go through them all
        for directory, repo_config in repo_sync_config.items():
            repo = repo_config["repo"]
            # If metadata_mirroring is enabled we cannot skip any syncs, because the generated
            # publication needs to contain exactly the same metadata at the same paths.
            if not mirror_metadata and optimize and repo_config["should_skip"]:
                skipped_syncs += 1
                repo_sync_results[directory] = repo.latest_version()
                continue

            stage = RpmFirstStage(
                remote,
                repo,
                deferred_download,
                mirror_metadata,
                skip_types=skip_types,
                new_url=repo_config["url"],
                treeinfo=(treeinfo if not is_subrepo(directory) else None),
                namespace=directory,
            )

            dv = RpmDeclarativeVersion(first_stage=stage, repository=repo, mirror=mirror)
            repo_version = dv.create() or repo.latest_version()

            repo_config["sync_details"]["most_recent_version"] = repo_version.number
            repo.last_sync_details = repo_config["sync_details"]
            repo.save()

            repo_sync_results[directory] = repo_version

    if skipped_syncs:
        with ProgressReport(
            message="Skipping Sync (no change from previous sync)", code="sync.was_skipped"
        ) as pb:
            pb.done = skipped_syncs
            pb.total = len(repo_sync_config)

    if mirror_metadata:
        with RpmPublication.create(
            repo_sync_results[PRIMARY_REPO], pass_through=False
        ) as publication:
            for (path, repo_version) in repo_sync_results.items():
                add_metadata_to_publication(publication, repo_version, prefix=path)

    return repo_sync_results[PRIMARY_REPO]


class RpmDeclarativeVersion(DeclarativeVersion):
    """
    Subclassed Declarative version creates a custom pipeline for RPM sync.
    """

    def pipeline_stages(self, new_version):
        """
        Build a list of stages feeding into the ContentUnitAssociation stage.

        This defines the "architecture" of the entire sync.

        Args:
            new_version (:class:`~pulpcore.plugin.models.RepositoryVersion`): The
                new repository version that is going to be built.

        Returns:
            list: List of :class:`~pulpcore.plugin.stages.Stage` instances

        """
        pipeline = [
            self.first_stage,
            QueryExistingArtifacts(),
            ArtifactDownloader(),
            ArtifactSaver(),
            QueryExistingContents(),
            RpmContentSaver(),
            RpmInterrelateContent(),
            RemoteArtifactSaver(fix_mismatched_remote_artifacts=True),
        ]
        return pipeline


class RpmFirstStage(Stage):
    """
    First stage of the Asyncio Stage Pipeline.

    Create a :class:`~pulpcore.plugin.stages.DeclarativeContent` object for each content unit
    that should exist in the new :class:`~pulpcore.plugin.models.RepositoryVersion`.
    """

    def __init__(
        self,
        remote,
        repository,
        deferred_download,
        mirror_metadata,
        skip_types=None,
        new_url=None,
        treeinfo=None,
        namespace="",
    ):
        """
        The first stage of a pulp_rpm sync pipeline.

        Args:
            remote (RpmRemote or UlnRemote): The remote data to be used when syncing
            repository (RpmRepository): The repository to be compared when optimizing sync
            deferred_download (bool): If True the downloading will not happen now. If False, it will
                happen immediately.
            mirror_metadata (bool): Influences which metadata files are downloaded and what
                is done with them.

        Keyword Args:
            skip_types (list): List of content to skip
            new_url(str): URL to replace remote url
            treeinfo(dict): Treeinfo data
            namespace(str): Path where this repo is located relative to some parent repo.

        """
        super().__init__()

        self.remote = remote
        self.repository = repository
        self.deferred_download = deferred_download
        self.mirror_metadata = mirror_metadata

        # How many directories deep this repo is nested within another repo (if at all).
        # Backwards relative paths that are shallower than this depth are permitted (in mirror
        # mode), to accomodate sub-repos which re-use packages from the parent repo.
        self.namespace_depth = 0 if not namespace else len(namespace.strip("/").split("/"))

        self.treeinfo = treeinfo
        self.skip_types = [] if skip_types is None else skip_types

        self.remote_url = new_url or self.remote.url

        self.nevra_to_module = defaultdict(dict)
        self.pkgname_to_groups = defaultdict(list)

    def is_illegal_relative_path(self, path):
        """Whether a relative path points outside the repository being synced."""
        return path.count("../") > self.namespace_depth

    @staticmethod
    async def parse_updateinfo(updateinfo_xml_path):
        """
        Parse updateinfo.xml to extact update info.

        Args:
            updateinfo_xml_path: a path to a downloaded updateinfo.xml

        Returns:
            :obj:`list` of :obj:`createrepo_c.UpdateRecord`: parsed update records

        """
        uinfo = cr.UpdateInfo()

        # TODO: handle parsing errors/warnings, warningcb callback can be used
        cr.xml_parse_updateinfo(updateinfo_xml_path, uinfo)
        return uinfo.updates

    async def run(self):
        """Build `DeclarativeContent` from the repodata."""
        with tempfile.TemporaryDirectory("."):
            progress_data = dict(
                message="Downloading Metadata Files", code="sync.downloading.metadata"
            )
            async with ProgressReport(**progress_data) as metadata_pb:
                # download repomd.xml
                downloader = self.remote.get_downloader(
                    url=urlpath_sanitize(self.remote_url, "repodata/repomd.xml")
                )
                result = await downloader.run()
                store_metadata_for_mirroring(self.repository, result.path, "repodata/repomd.xml")
                await metadata_pb.aincrement()

                repomd_path = result.path
                repomd = cr.Repomd(repomd_path)

                checksum_types = {}
                repomd_downloaders = {}
                repomd_files = {}

                types_to_download = (
                    set(PACKAGE_REPODATA)
                    | set(UPDATE_REPODATA)
                    | set(COMPS_REPODATA)
                    | set(MODULAR_REPODATA)
                )

                async def run_repomdrecord_download(name, location_href, downloader):
                    result = await downloader.run()
                    return name, location_href, result

                file_extension = [
                    record.location_href for record in repomd.records if record.type == "primary"
                ][0].split(".")[-1]

                for record in repomd.records:
                    record_checksum_type = getattr(CHECKSUM_TYPES, record.checksum_type.upper())
                    checksum_types[record.type] = record_checksum_type
                    record.checksum_type = record_checksum_type

                    if self.mirror_metadata:
                        uses_base_url = record.location_base
                        illegal_relative_path = self.is_illegal_relative_path(record.location_href)

                        if uses_base_url or illegal_relative_path or record.type == "prestodelta":
                            raise ValueError(MIRROR_INCOMPATIBLE_REPO_ERR_MSG)

                    if not self.mirror_metadata and record.type not in types_to_download:
                        continue

                    base_url = record.location_base or self.remote_url
                    downloader = self.remote.get_downloader(
                        url=urlpath_sanitize(base_url, record.location_href),
                        expected_size=record.size,
                        expected_digests={record_checksum_type: record.checksum},
                    )
                    repomd_downloaders[record.type] = asyncio.ensure_future(
                        run_repomdrecord_download(record.type, record.location_href, downloader)
                    )

                self.repository.original_checksum_types = checksum_types

                try:
                    for future in asyncio.as_completed(list(repomd_downloaders.values())):
                        name, location_href, result = await future
                        store_metadata_for_mirroring(self.repository, result.path, location_href)
                        repomd_files[name] = result
                        await metadata_pb.aincrement()
                except ClientResponseError as exc:
                    raise HTTPNotFound(reason=_("File not found: {}".format(exc.request_info.url)))
                except FileNotFoundError:
                    raise

                if self.mirror_metadata:
                    # optional signature and key files for repomd metadata
                    for file_href in ["repodata/repomd.xml.asc", "repodata/repomd.xml.key"]:
                        try:
                            downloader = self.remote.get_downloader(
                                url=urlpath_sanitize(self.remote_url, file_href),
                                silence_errors_for_response_status_codes={403, 404},
                            )
                            result = await downloader.run()
                            store_metadata_for_mirroring(self.repository, result.path, file_href)
                            await metadata_pb.aincrement()
                        except (ClientResponseError, FileNotFoundError):
                            pass

                    # extra files to copy, e.g. EULA, LICENSE
                    try:
                        downloader = self.remote.get_downloader(
                            url=urlpath_sanitize(self.remote_url, "extra_files.json"),
                            silence_errors_for_response_status_codes={403, 404},
                        )
                        result = await downloader.run()
                        store_metadata_for_mirroring(
                            self.repository, result.path, "extra_files.json"
                        )
                        await metadata_pb.aincrement()
                    except (ClientResponseError, FileNotFoundError):
                        pass
                    else:
                        try:
                            with open(result.path, "r") as f:
                                extra_files = json.loads(f.read())
                                for data in extra_files["data"]:
                                    filtered_checksums = {
                                        digest: value
                                        for digest, value in data["checksums"].items()
                                        if digest in settings.ALLOWED_CONTENT_CHECKSUMS
                                    }
                                    downloader = self.remote.get_downloader(
                                        url=urlpath_sanitize(self.remote_url, data["file"]),
                                        expected_size=data["size"],
                                        expected_digests=filtered_checksums,
                                    )
                                    result = await downloader.run()
                                    store_metadata_for_mirroring(
                                        self.repository, result.path, data["file"]
                                    )
                                    await metadata_pb.aincrement()
                        except ClientResponseError as exc:
                            raise HTTPNotFound(
                                reason=_("File not found: {}".format(exc.request_info.url))
                            )
                        except FileNotFoundError:
                            raise

            await self.parse_repository_metadata(repomd, repomd_files, file_extension)

    async def parse_distribution_tree(self):
        """Parse content from the file treeinfo if present."""
        if self.treeinfo:
            d_artifacts = [
                DeclarativeArtifact(
                    artifact=Artifact(),
                    url=urlpath_sanitize(self.remote_url, self.treeinfo["filename"]),
                    relative_path=".treeinfo",
                    remote=self.remote,
                    deferred_download=False,
                )
            ]
            for path, checksum in self.treeinfo["download"]["images"].items():
                artifact = Artifact(**checksum)
                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=urlpath_sanitize(self.remote_url, path),
                    relative_path=path,
                    remote=self.remote,
                    deferred_download=self.deferred_download,
                )
                d_artifacts.append(da)

            distribution_tree = DistributionTree(**self.treeinfo["distribution_tree"])
            dc = DeclarativeContent(content=distribution_tree, d_artifacts=d_artifacts)
            dc.extra_data = self.treeinfo
            await self.put(dc)

    async def parse_repository_metadata(self, repomd, metadata_results, file_extension):
        """Parse repository metadata."""
        needed_metadata = set(PACKAGE_REPODATA) - set(metadata_results.keys())

        if needed_metadata:
            raise FileNotFoundError(
                _("XML file(s): {filenames} not found").format(filenames=", ".join(needed_metadata))
            )

        await self.parse_distribution_tree()

        # modularity-parsing MUST COME BEFORE package-parsing!
        # The only way to know if a package is 'modular' in a repo, is to
        # know that it is referenced in modulemd.
        modulemd_list = []
        modulemd_result = metadata_results.get("modules", None)
        if modulemd_result:
            modulemd_list = await self.parse_modules_metadata(modulemd_result)

        # **Now** we can successfully parse package-metadata
        await self.parse_packages(
            metadata_results["primary"],
            metadata_results["filelists"],
            metadata_results["other"],
            file_extension=file_extension,
        )

        groups_list = []
        comps_result = metadata_results.get("group", None)
        if comps_result:
            groups_list = await self.parse_packages_components(comps_result)

        updateinfo_result = metadata_results.get("updateinfo", None)
        if updateinfo_result:
            await self.parse_advisories(updateinfo_result)

        # now send modules and groups down the pipeline since all relations have been set up
        for modulemd_dc in modulemd_list:
            await self.put(modulemd_dc)

        for group_dc in groups_list:
            await self.put(group_dc)

        record_types = (
            set(PACKAGE_REPODATA)
            | set(PACKAGE_DB_REPODATA)
            | set(UPDATE_REPODATA)
            | set(COMPS_REPODATA)
            | set(MODULAR_REPODATA)
        )

        for record in repomd.records:
            should_skip = False
            if record.type not in record_types:
                for suffix in ["_zck", "_gz", "_xz"]:
                    if suffix in record.type:
                        should_skip = True
                if record.type in ["prestodelta"]:
                    should_skip = True

                if should_skip:
                    continue

                sanitized_checksum_type = getattr(CHECKSUM_TYPES, record.checksum_type.upper())
                file_data = {sanitized_checksum_type: record.checksum, "size": record.size}
                da = DeclarativeArtifact(
                    artifact=Artifact(**file_data),
                    url=urlpath_sanitize(self.remote_url, record.location_href),
                    relative_path=record.location_href,
                    remote=self.remote,
                    deferred_download=False,
                )
                repo_metadata_file = RepoMetadataFile(
                    data_type=record.type,
                    checksum_type=sanitized_checksum_type,
                    checksum=record.checksum,
                    relative_path=record.location_href,
                )
                dc = DeclarativeContent(content=repo_metadata_file, d_artifacts=[da])
                await self.put(dc)

    async def parse_modules_metadata(self, modulemd_result):
        """Parse modules' metadata which define what packages are built for specific releases."""
        modulemd_index = mmdlib.ModuleIndex.new()
        modulemd_index.update_from_file(modulemd_result.path, True)

        modulemd_names = modulemd_index.get_module_names() or []
        modulemd_all = parse_modulemd(modulemd_names, modulemd_index)
        modulemd_list = []

        # Parsing modules happens all at one time, and from here on no useful work happens.
        # So just report that it finished this stage.
        modulemd_pb_data = {"message": "Parsed Modulemd", "code": "sync.parsing.modulemds"}
        async with ProgressReport(**modulemd_pb_data) as modulemd_pb:
            modulemd_total = len(modulemd_all)
            modulemd_pb.total = modulemd_total
            modulemd_pb.done = modulemd_total

        for modulemd in modulemd_all:
            artifact = modulemd.pop("artifact")
            relative_path = "{}{}{}{}{}snippet".format(
                modulemd[PULP_MODULE_ATTR.NAME],
                modulemd[PULP_MODULE_ATTR.STREAM],
                modulemd[PULP_MODULE_ATTR.VERSION],
                modulemd[PULP_MODULE_ATTR.CONTEXT],
                modulemd[PULP_MODULE_ATTR.ARCH],
            )
            da = DeclarativeArtifact(
                artifact=artifact, relative_path=relative_path, url=modulemd_result.url
            )
            modulemd_content = Modulemd(**modulemd)
            dc = DeclarativeContent(content=modulemd_content, d_artifacts=[da])
            dc.extra_data = defaultdict(list)

            # dc.content.artifacts are Modulemd artifacts
            for artifact in dc.content.artifacts:
                self.nevra_to_module.setdefault(artifact, set()).add(dc)
            modulemd_list.append(dc)

        # Parse modulemd default names
        modulemd_default_names = parse_defaults(modulemd_index)

        # Parsing module-defaults happens all at one time, and from here on no useful
        # work happens. So just report that it finished this stage.
        modulemd_defaults_pb_data = {
            "message": "Parsed Modulemd-defaults",
            "code": "sync.parsing.modulemd_defaults",
        }
        async with ProgressReport(**modulemd_defaults_pb_data) as modulemd_defaults_pb:
            modulemd_defaults_total = len(modulemd_default_names)
            modulemd_defaults_pb.total = modulemd_defaults_total
            modulemd_defaults_pb.done = modulemd_defaults_total

        default_content_dcs = []
        for default in modulemd_default_names:
            artifact = default.pop("artifact")
            relative_path = "{}{}snippet".format(
                default[PULP_MODULEDEFAULTS_ATTR.MODULE], default[PULP_MODULEDEFAULTS_ATTR.STREAM]
            )
            da = DeclarativeArtifact(
                artifact=artifact, relative_path=relative_path, url=modulemd_result.url
            )
            default_content = ModulemdDefaults(**default)
            default_content_dcs.append(
                DeclarativeContent(content=default_content, d_artifacts=[da])
            )

        if default_content_dcs:
            for default_content_dc in default_content_dcs:
                await self.put(default_content_dc)

        return modulemd_list

    async def parse_packages_components(self, comps_result):
        """Parse packages' components that define how are the packages bundled."""
        group_to_categories = defaultdict(list)

        group_to_environments = defaultdict(list)
        optionalgroup_to_environments = defaultdict(list)

        package_language_pack_dc = None
        dc_categories = []
        dc_environments = []
        dc_groups = []

        comps = libcomps.Comps()
        comps.fromxml_f(comps_result.path)

        async with ProgressReport(message="Parsed Comps", code="sync.parsing.comps") as comps_pb:
            comps_total = len(comps.groups) + len(comps.categories) + len(comps.environments)
            comps_pb.total = comps_total
            comps_pb.done = comps_total

        if comps.langpacks:
            langpack_dict = PackageLangpacks.libcomps_to_dict(comps.langpacks)
            packagelangpack = PackageLangpacks(
                matches=strdict_to_dict(comps.langpacks), digest=dict_digest(langpack_dict)
            )
            package_language_pack_dc = DeclarativeContent(content=packagelangpack)
            package_language_pack_dc.extra_data = defaultdict(list)

        # init categories declarative content
        if comps.categories:
            for category in comps.categories:
                category_dict = PackageCategory.libcomps_to_dict(category)
                category_dict["digest"] = dict_digest(category_dict)
                packagecategory = PackageCategory(**category_dict)
                dc = DeclarativeContent(content=packagecategory)
                dc.extra_data = defaultdict(list)

                if packagecategory.group_ids:
                    for group_id in packagecategory.group_ids:
                        group_to_categories[group_id["name"]].append(dc)
                dc_categories.append(dc)

        # init environments declarative content
        if comps.environments:
            for environment in comps.environments:
                environment_dict = PackageEnvironment.libcomps_to_dict(environment)
                environment_dict["digest"] = dict_digest(environment_dict)
                packageenvironment = PackageEnvironment(**environment_dict)
                dc = DeclarativeContent(content=packageenvironment)
                dc.extra_data = defaultdict(list)

                if packageenvironment.option_ids:
                    for option_id in packageenvironment.option_ids:
                        optionalgroup_to_environments[option_id["name"]].append(dc)

                if packageenvironment.group_ids:
                    for group_id in packageenvironment.group_ids:
                        group_to_environments[group_id["name"]].append(dc)

                dc_environments.append(dc)

        # init groups declarative content
        if comps.groups:
            for group in comps.groups:
                group_dict = PackageGroup.libcomps_to_dict(group)
                group_dict["digest"] = dict_digest(group_dict)
                packagegroup = PackageGroup(**group_dict)
                dc = DeclarativeContent(content=packagegroup)
                dc.extra_data = defaultdict(list)

                if packagegroup.packages:
                    for package in packagegroup.packages:
                        self.pkgname_to_groups[package["name"]].append(dc)

                if dc.content.id in group_to_categories.keys():
                    for dc_category in group_to_categories[dc.content.id]:
                        dc.extra_data["category_relations"].append(dc_category)
                        dc_category.extra_data["packagegroups"].append(dc)

                if dc.content.id in group_to_environments.keys():
                    for dc_environment in group_to_environments[dc.content.id]:
                        dc.extra_data["environment_relations"].append(dc_environment)
                        dc_environment.extra_data["packagegroups"].append(dc)

                if dc.content.id in optionalgroup_to_environments.keys():
                    for dc_environment in optionalgroup_to_environments[dc.content.id]:
                        dc.extra_data["env_relations_optional"].append(dc_environment)
                        dc_environment.extra_data["optionalgroups"].append(dc)

                dc_groups.append(dc)

        if package_language_pack_dc:
            await self.put(package_language_pack_dc)

        for dc_category in dc_categories:
            await self.put(dc_category)

        for dc_environment in dc_environments:
            await self.put(dc_environment)

        return dc_groups

    async def parse_packages(self, primary_xml, filelists_xml, other_xml, file_extension="gz"):
        """Parse packages from the remote repository."""
        parser = MetadataParser.from_metadata_files(
            primary_xml.path, filelists_xml.path, other_xml.path
        )

        progress_data = {
            "message": "Parsed Packages",
            "code": "sync.parsing.packages",
            "total": parser.count_packages(),
        }

        async with ProgressReport(**progress_data) as packages_pb:
            # skip SRPM if defined
            skip_srpms = "srpm" in self.skip_types and not self.mirror_metadata

            async def on_package(pkg):
                """Callback when handling a completed package.

                Args:
                    pkg (createrepo_c.Package): A completed createrepo_c package.
                """
                if self.mirror_metadata:
                    uses_base_url = pkg.location_base
                    illegal_relative_path = self.is_illegal_relative_path(pkg.location_href)

                    if uses_base_url or illegal_relative_path:
                        raise ValueError(MIRROR_INCOMPATIBLE_REPO_ERR_MSG)

                package = Package(**Package.createrepo_to_dict(pkg))
                base_url = pkg.location_base or self.remote_url
                url = urlpath_sanitize(base_url, package.location_href)
                del pkg  # delete it as soon as we're done with it

                store_package_for_mirroring(self.repository, package.pkgId, package.location_href)
                artifact = Artifact(size=package.size_package)
                checksum_type = getattr(CHECKSUM_TYPES, package.checksum_type.upper())
                setattr(artifact, checksum_type, package.pkgId)
                filename = os.path.basename(package.location_href)
                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=url,
                    relative_path=filename,
                    remote=self.remote,
                    deferred_download=self.deferred_download,
                )
                dc = DeclarativeContent(content=package, d_artifacts=[da])
                dc.extra_data = defaultdict(list)

                # find if a package relates to a modulemd
                if dc.content.nevra in self.nevra_to_module.keys():
                    dc.content.is_modular = True
                    for dc_modulemd in self.nevra_to_module[dc.content.nevra]:
                        dc.extra_data["modulemd_relation"].append(dc_modulemd)
                        dc_modulemd.extra_data["package_relation"].append(dc)

                if dc.content.name in self.pkgname_to_groups.keys():
                    for dc_group in self.pkgname_to_groups[dc.content.name]:
                        dc.extra_data["group_relations"].append(dc_group)
                        dc_group.extra_data["related_packages"].append(dc)

                await packages_pb.aincrement()  # TODO: don't do this for every individual package
                await self.put(dc)

            if settings.RPM_ITERATIVE_PARSING:
                for pkg in parser.parse_packages_iterative(file_extension, skip_srpms=skip_srpms):
                    await on_package(pkg)
            else:
                for pkg in parser.parse_packages(skip_srpms=skip_srpms):
                    await on_package(pkg)

    async def parse_advisories(self, result):
        """Parse advisories from the remote repository."""
        updateinfo_xml_path = result.path

        updates = await RpmFirstStage.parse_updateinfo(updateinfo_xml_path)
        progress_data = {
            "message": "Parsed Advisories",
            "code": "sync.parsing.advisories",
            "total": len(updates),
        }
        async with ProgressReport(**progress_data) as advisories_pb:
            for update in updates:
                update_record = UpdateRecord(**UpdateRecord.createrepo_to_dict(update))
                update_record.digest = hash_update_record(update)
                future_relations = {"collections": defaultdict(list), "references": []}

                for collection in update.collections:
                    coll_dict = UpdateCollection.createrepo_to_dict(collection)
                    coll = UpdateCollection(**coll_dict)

                    for package in collection.packages:
                        pkg_dict = UpdateCollectionPackage.createrepo_to_dict(package)
                        pkg = UpdateCollectionPackage(**pkg_dict)
                        future_relations["collections"][coll].append(pkg)

                for reference in update.references:
                    reference_dict = UpdateReference.createrepo_to_dict(reference)
                    ref = UpdateReference(**reference_dict)
                    future_relations["references"].append(ref)

                await advisories_pb.aincrement()
                dc = DeclarativeContent(content=update_record)
                dc.extra_data = future_relations
                await self.put(dc)


class RpmInterrelateContent(Stage):
    """
    A stage that creates relationships between Packages and other related types.

    This stage creates relationships Packages and Modulemd, PackageGroup, PackageCatagory and
    PackageEnvironment models.
    """

    async def run(self):
        """
        Create all the relationships.
        """
        async for batch in self.batches():

            def process_batch():
                with transaction.atomic():
                    ModulemdPackages = Modulemd.packages.through

                    modulemd_pkgs_to_save = []

                    for d_content in batch:
                        if d_content is None:
                            continue

                        if isinstance(d_content.content, Modulemd):
                            for pkg in d_content.extra_data["package_relation"]:
                                if not pkg.content._state.adding:
                                    module_package = ModulemdPackages(
                                        package_id=pkg.content.pk,
                                        modulemd_id=d_content.content.pk,
                                    )
                                    modulemd_pkgs_to_save.append(module_package)

                        elif isinstance(d_content.content, Package):
                            for modulemd in d_content.extra_data["modulemd_relation"]:
                                if not modulemd.content._state.adding:
                                    module_package = ModulemdPackages(
                                        package_id=d_content.content.pk,
                                        modulemd_id=modulemd.content.pk,
                                    )
                                    modulemd_pkgs_to_save.append(module_package)

                    if modulemd_pkgs_to_save:
                        ModulemdPackages.objects.bulk_create(
                            modulemd_pkgs_to_save, ignore_conflicts=True
                        )

            await sync_to_async(process_batch)()
            for declarative_content in batch:
                await self.put(declarative_content)


class RpmContentSaver(ContentSaver):
    """
    A modification of ContentSaver stage that additionally saves RPM plugin specific items.

    Saves UpdateCollection, UpdateCollectionPackage, UpdateReference objects related to
    the UpdateRecord content unit.
    """

    def _post_save(self, batch):
        """
        Save a batch of UpdateCollection, UpdateCollectionPackage, UpdateReference objects.

        When it has a treeinfo file, save a batch of Addon, Checksum, Image, Variant objects.

        Args:
            batch (list of :class:`~pulpcore.plugin.stages.DeclarativeContent`): The batch of
                :class:`~pulpcore.plugin.stages.DeclarativeContent` objects to be saved.

        """

        def _handle_distribution_tree(declarative_content):
            distribution_tree = declarative_content.content
            treeinfo_data = declarative_content.extra_data

            if treeinfo_data["created"] > distribution_tree.pulp_created:
                return

            resources = ["addons", "variants"]
            for resource_name in resources:
                for resource_id, resource in treeinfo_data[resource_name].items():
                    key = resource["repository"]
                    del resource["repository"]
                    resource["repository_id"] = treeinfo_data["repositories"][key]

            addons = []
            checksums = []
            images = []
            variants = []

            for addon_id, addon in treeinfo_data["addons"].items():
                instance = Addon(**addon)
                instance.distribution_tree = distribution_tree
                addons.append(instance)

            for checksum in treeinfo_data["checksums"]:
                instance = Checksum(**checksum)
                instance.distribution_tree = distribution_tree
                checksums.append(instance)

            for image in treeinfo_data["images"]:
                instance = Image(**image)
                instance.distribution_tree = distribution_tree
                images.append(instance)

            for variant_id, variant in treeinfo_data["variants"].items():
                instance = Variant(**variant)
                instance.distribution_tree = distribution_tree
                variants.append(instance)

            if addons:
                Addon.objects.bulk_create(addons, ignore_conflicts=True)
            if checksums:
                Checksum.objects.bulk_create(checksums, ignore_conflicts=True)
            if images:
                Image.objects.bulk_create(images, ignore_conflicts=True)
            if variants:
                Variant.objects.bulk_create(variants, ignore_conflicts=True)

        update_collection_to_save = []
        update_references_to_save = []
        update_collection_packages_to_save = []
        seen_updaterecords = []

        for declarative_content in batch:
            if declarative_content is None:
                continue

            if isinstance(declarative_content.content, DistributionTree):
                _handle_distribution_tree(declarative_content)
                continue
            elif isinstance(declarative_content.content, UpdateRecord):
                update_record = declarative_content.content

                relations_exist = (
                    update_record.collections.count() or update_record.references.count()
                )
                if relations_exist:
                    # existing content which was retrieved from the db at earlier stages
                    continue

                # if there are same update_records in a batch, the relations to the references
                # and collections will be duplicated, if there are 3 same update_record,
                # there will be 3 sets of relations and collections.
                # It can happen easily during pulp 2to3 migration, or in case of a bad repo.
                if update_record.digest in seen_updaterecords:
                    continue
                seen_updaterecords.append(update_record.digest)

                future_relations = declarative_content.extra_data
                update_collections = future_relations.get("collections", {})
                update_references = future_relations.get("references", [])

                for update_collection, packages in update_collections.items():
                    update_collection.update_record = update_record
                    update_collection_to_save.append(update_collection)

                    for update_collection_package in packages:
                        update_collection_package.update_collection = update_collection
                        update_collection_packages_to_save.append(update_collection_package)

                for update_reference in update_references:
                    update_reference.update_record = update_record
                    update_references_to_save.append(update_reference)

        if update_collection_to_save:
            UpdateCollection.objects.bulk_create(update_collection_to_save, ignore_conflicts=True)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(
                update_collection_packages_to_save, ignore_conflicts=True
            )

        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save, ignore_conflicts=True)
