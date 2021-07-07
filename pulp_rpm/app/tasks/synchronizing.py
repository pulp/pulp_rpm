import asyncio
import collections
import json
import logging
import os
import re
import tempfile

from collections import defaultdict
from gettext import gettext as _  # noqa:F401

from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.db import transaction

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
from pulp_rpm.app.metadata_parsing import iterative_files_changelog_parser

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


def store_metadata_for_mirroring(repo, dl_result, relative_path):
    """Used to store data about the downloaded metadata for mirror-publishing after the sync.

    Args:
        repo: Which repository the metadata is associated with
        dl_result: The DownloadResult from downloading the metadata
        relative_path: The relative path to the metadata file within the repository
    """
    global metadata_files_for_mirroring
    metadata_files_for_mirroring[str(repo.pk)][relative_path] = dl_result


def store_package_for_mirroring(repo, pkgid, location_href):
    """Used to store data about the packages for mirror-publishing after the sync.

    Args:
        repo: Which repository the metadata is associated with
        pkgid: The checksum of the package
        location_href: The relative path to the package within the repository
    """
    global pkgid_to_location_href
    pkgid_to_location_href[str(repo.pk)][pkgid] = location_href


def mirrored_publish(version):
    """Create a mirrored publication for the given repository version.

    Uses the `metadata_files` global data.

    Args:
        version: The repository version to mirror-publish
    """
    with RpmPublication.create(version, pass_through=False) as publication:
        repo_metadata_files = metadata_files_for_mirroring[str(version.repository.pk)]

        has_repomd_signature = "repodata/repomd.xml.asc" in repo_metadata_files.keys()
        has_sqlite = any([".sqlite" in href for href in repo_metadata_files.keys()])

        publication.package_checksum_type = CHECKSUM_TYPES.UNKNOWN
        publication.metadata_checksum_type = CHECKSUM_TYPES.UNKNOWN
        publication.gpgcheck = 0
        publication.repo_gpgcheck = has_repomd_signature
        publication.sqlite_metadata = has_sqlite

        for (relative_path, result) in repo_metadata_files.items():
            PublishedMetadata.create_from_file(
                file=File(open(result.path, "rb")),
                relative_path=relative_path,
                publication=publication,
            )

        published_artifacts = []
        pkg_data = (
            ContentArtifact.objects.filter(
                content__in=version.content, content__pulp_type=Package.get_pulp_type()
            )
            .select_related("content__rpm_package")
            .only("pk", "artifact", "content", "content__rpm_package__pkgId")
        )
        for ca in pkg_data.iterator():
            pa = PublishedArtifact(
                content_artifact=ca,
                relative_path=pkgid_to_location_href[str(version.repository.pk)][
                    ca.content.rpm_package.pkgId
                ],
                publication=publication,
            )
            published_artifacts.append(pa)

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
    downloader = remote.get_downloader(url=remote.url.rstrip("/"))
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


def is_optimized_sync(repository, remote, url):
    """
    Check whether it is possible to optimize the synchronization or not.

    Caution: we are not storing when the remote was last updated, so the order of this
    logic must remain in this order where we first check the version number as other
    changes than sync could have taken place such that the date or repo version will be
    different from last sync.

    Args:
        repository(RpmRepository): An RpmRepository to check optimization for.
        remote(RpmRemote or UlnRemote): An RPMRemote or UlnRemote to check optimization for.
        url(str): A remote repository URL.

    Returns:
        bool: True, if sync is optimized; False, otherwise.

    """
    with tempfile.TemporaryDirectory("."):
        try:
            result = get_repomd_file(remote, url)
            repomd_path = result.path
            repomd = cr.Repomd(repomd_path)
            repomd_checksum = get_sha256(repomd_path)
        except Exception:
            return False

    is_optimized = (
        repository.last_sync_remote
        and remote.pk == repository.last_sync_remote.pk
        and repository.last_sync_repo_version == repository.latest_version().number
        and remote.pulp_last_updated <= repository.latest_version().pulp_created
        and is_previous_version(repomd.revision, repository.last_sync_revision_number)
        and repository.last_sync_repomd_checksum == repomd_checksum
    )

    return is_optimized


def synchronize(remote_pk, repository_pk, mirror, skip_types, optimize):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (bool): Mirror mode.
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
                store_metadata_for_mirroring(repository, result, namespace)
            except FileNotFoundError:
                continue

            treeinfo = PulpTreeInfo()
            treeinfo.load(f=result.path)
            treeinfo_parsed = treeinfo.parsed_sections()
            sha256 = result.artifact_attributes["sha256"]
            treeinfo_serialized = TreeinfoData(treeinfo_parsed).to_dict(
                hash=sha256, filename=namespace
            )
            break

        return treeinfo_serialized

    with tempfile.TemporaryDirectory("."):
        remote_url = fetch_remote_url(remote)

        if optimize and is_optimized_sync(repository, remote, remote_url):
            with ProgressReport(
                message="Skipping Sync (no change from previous sync)", code="sync.was_skipped"
            ) as pb:
                pb.done = 1
            return

        treeinfo = get_treeinfo_data(remote, remote_url)

    if treeinfo:
        treeinfo["repositories"] = {}
        for repodata in set(treeinfo["download"]["repodatas"]):
            if repodata == DIST_TREE_MAIN_REPO_PATH:
                treeinfo["repositories"].update({repodata: None})
                continue
            name = f"{repodata}-{treeinfo['hash']}"
            sub_repo, created = RpmRepository.objects.get_or_create(name=name, sub_repo=True)
            if created:
                sub_repo.save()
            directory = treeinfo["repo_map"][repodata]
            treeinfo["repositories"].update({directory: str(sub_repo.pk)})
            path = f"{repodata}/"
            new_url = urlpath_sanitize(remote_url, path)

            try:
                with tempfile.TemporaryDirectory("."):
                    get_repomd_file(remote, new_url)
            except ClientResponseError as exc:
                if exc.status == 404:
                    continue
                raise exc
            else:
                if optimize and is_optimized_sync(sub_repo, remote, new_url):
                    continue
                stage = RpmFirstStage(
                    remote,
                    sub_repo,
                    deferred_download,
                    mirror,
                    skip_types=skip_types,
                    new_url=new_url,
                )
                dv = RpmDeclarativeVersion(first_stage=stage, repository=sub_repo)
                subrepo_version = dv.create()
                if subrepo_version:
                    sub_repo.last_sync_remote = remote
                    sub_repo.last_sync_repo_version = sub_repo.latest_version().number
                    sub_repo.save()
                    if mirror:
                        mirrored_publish(subrepo_version)

    first_stage = RpmFirstStage(
        remote,
        repository,
        deferred_download,
        mirror,
        skip_types=skip_types,
        treeinfo=treeinfo,
        new_url=remote_url,
    )
    dv = RpmDeclarativeVersion(first_stage=first_stage, repository=repository, mirror=mirror)
    version = dv.create()
    if version:
        repository.last_sync_remote = remote
        repository.last_sync_repo_version = version.number
        repository.save()
        if mirror:
            mirrored_publish(version)
    return version


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
            RemoteArtifactSaver(),
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
        mirror,
        skip_types=None,
        new_url=None,
        treeinfo=None,
    ):
        """
        The first stage of a pulp_rpm sync pipeline.

        Args:
            remote (RpmRemote or UlnRemote): The remote data to be used when syncing
            repository (RpmRepository): The repository to be compared when optimizing sync
            deferred_download (bool): if True the downloading will not happen now. If False, it will
                happen immediately.

        Keyword Args:
            skip_types (list): List of content to skip
            new_url(str): URL to replace remote url
            treeinfo(dict): Treeinfo data

        """
        super().__init__()

        self.remote = remote
        self.repository = repository
        self.deferred_download = deferred_download
        self.mirror = mirror

        self.treeinfo = treeinfo
        self.skip_types = [] if skip_types is None else skip_types

        self.remote_url = new_url or self.remote.url

        self.nevra_to_module = defaultdict(dict)
        self.pkgname_to_groups = defaultdict(list)

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

    @staticmethod
    async def parse_repodata(primary_xml_path, filelists_xml_path, other_xml_path):
        """
        Parse repodata to extract package info.

        Args:
            primary_xml_path(str): a path to a downloaded primary.xml
            filelists_xml_path(str): a path to a downloaded filelists.xml
            other_xml_path(str): a path to a downloaded other.xml

        Returns:
            dict: createrepo_c package objects with the pkgId as a key

        """

        def pkgcb(pkg):
            """
            A callback which is used when a whole package entry in xml is parsed.

            Args:
                pkg(preaterepo_c.Package): a parsed metadata for a package

            """
            packages[pkg.pkgId] = pkg

        def newpkgcb(pkgId, name, arch):
            """
            A callback which is used when a new package entry is encountered.

            Only opening <package> element is parsed at that moment.
            This function has to return a package which parsed data will be added to
            or None if a package should be skipped.

            pkgId, name and arch of a package can be used to skip further parsing. Available
            only for filelists.xml and other.xml.

            Args:
                pkgId(str): pkgId of a package
                name(str): name of a package
                arch(str): arch of a package

            Returns:
                createrepo_c.Package: a package which parsed data should be added to.

                If None is returned, further parsing of a package will be skipped.

            """
            return packages.get(pkgId, None)

        packages = collections.OrderedDict()

        # TODO: handle parsing errors/warnings, warningcb callback can be used below
        cr.xml_parse_primary(primary_xml_path, pkgcb=pkgcb, do_files=False)

        # only left behind to make swapping back for testing easier - we are doing our own separate
        # parsing of other.xml and filelists.xml
        # cr.xml_parse_filelists(filelists_xml_path, newpkgcb=newpkgcb)
        # cr.xml_parse_other(other_xml_path, newpkgcb=newpkgcb)
        return packages

    async def run(self):
        """Build `DeclarativeContent` from the repodata."""
        with tempfile.TemporaryDirectory("."):
            progress_data = dict(
                message="Downloading Metadata Files", code="sync.downloading.metadata"
            )
            with ProgressReport(**progress_data) as metadata_pb:
                # download repomd.xml
                downloader = self.remote.get_downloader(
                    url=urlpath_sanitize(self.remote_url, "repodata/repomd.xml")
                )
                result = await downloader.run()
                store_metadata_for_mirroring(self.repository, result, "repodata/repomd.xml")
                metadata_pb.increment()

                repomd_path = result.path
                repomd = cr.Repomd(repomd_path)

                self.repository.last_sync_revision_number = repomd.revision
                self.repository.last_sync_repomd_checksum = get_sha256(repomd_path)

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

                    if not self.mirror and record.type not in types_to_download:
                        continue

                    downloader = self.remote.get_downloader(
                        url=urlpath_sanitize(self.remote_url, record.location_href),
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
                        store_metadata_for_mirroring(self.repository, result, location_href)
                        repomd_files[name] = result
                        metadata_pb.increment()
                except ClientResponseError as exc:
                    raise HTTPNotFound(reason=_("File not found: {}".format(exc.request_info.url)))
                except FileNotFoundError:
                    raise

                if self.mirror:
                    # optional signature and key files for repomd metadata
                    for file_href in ["repodata/repomd.xml.asc", "repodata/repomd.xml.key"]:
                        try:
                            downloader = self.remote.get_downloader(
                                url=urlpath_sanitize(self.remote_url, file_href)
                            )
                            result = await downloader.run()
                            store_metadata_for_mirroring(self.repository, result, file_href)
                            metadata_pb.increment()
                        except (ClientResponseError, FileNotFoundError):
                            pass

                    # extra files to copy, e.g. EULA, LICENSE
                    try:
                        downloader = self.remote.get_downloader(
                            url=urlpath_sanitize(self.remote_url, "extra_files.json")
                        )
                        result = await downloader.run()
                        store_metadata_for_mirroring(self.repository, result, "extra_files.json")
                        metadata_pb.increment()
                    except (ClientResponseError, FileNotFoundError):
                        pass
                    else:
                        try:
                            with open(result.path, "r") as f:
                                extra_files = json.loads(f.read())
                                for data in extra_files["data"]:
                                    downloader = self.remote.get_downloader(
                                        url=urlpath_sanitize(self.remote_url, data["file"]),
                                        expected_size=data["size"],
                                        expected_digests=data["checksums"],
                                    )
                                    result = await downloader.run()
                                    store_metadata_for_mirroring(
                                        self.repository, result, data["file"]
                                    )
                                    metadata_pb.increment()
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

                file_data = {record.checksum_type: record.checksum, "size": record.size}
                da = DeclarativeArtifact(
                    artifact=Artifact(**file_data),
                    url=urlpath_sanitize(self.remote_url, record.location_href),
                    relative_path=record.location_href,
                    remote=self.remote,
                    deferred_download=False,
                )
                repo_metadata_file = RepoMetadataFile(
                    data_type=record.type,
                    checksum_type=record.checksum_type,
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
        with ProgressReport(**modulemd_pb_data) as modulemd_pb:
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
        with ProgressReport(**modulemd_defaults_pb_data) as modulemd_defaults_pb:
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

        with ProgressReport(message="Parsed Comps", code="sync.parsing.comps") as comps_pb:
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
        packages = await RpmFirstStage.parse_repodata(
            primary_xml.path, filelists_xml.path, other_xml.path
        )

        # skip SRPM if defined
        if "srpm" in self.skip_types and not self.mirror:
            packages = collections.OrderedDict(
                (pkgId, pkg) for pkgId, pkg in packages.items() if pkg.arch != "src"
            )

        progress_data = {
            "message": "Parsed Packages",
            "code": "sync.parsing.packages",
            "total": len(packages),
        }

        extra_repodata_parser = iterative_files_changelog_parser(
            file_extension, filelists_xml.path, other_xml.path
        )
        seen_pkgids = set()
        with ProgressReport(**progress_data) as packages_pb:
            while True:
                try:
                    (pkgid, pkg) = packages.popitem(last=False)
                except KeyError:
                    break

                while True:
                    pkgid_extra, files, changelogs = next(extra_repodata_parser)
                    if pkgid_extra in seen_pkgids:
                        # This is a dirty hack to handle cases that "shouldn't" happen.
                        # Sometimes repositories have packages listed twice under the same pkgid.
                        # This is a problem because the primary.xml parsing deduplicates the
                        # entries by placing them into a dict keyed by pkgid. So if the iterative
                        # parser(s) run into a package we've seen before, we should skip it and
                        # move on.
                        continue
                    else:
                        seen_pkgids.add(pkgid)
                        break

                assert pkgid == pkgid_extra, (
                    "Package id from primary metadata ({}), does not match package id "
                    "from filelists, other metadata ({})"
                ).format(pkgid, pkgid_extra)

                pkg.files = files
                pkg.changelogs = changelogs
                package = Package(**Package.createrepo_to_dict(pkg))
                del pkg

                store_package_for_mirroring(self.repository, package.pkgId, package.location_href)
                artifact = Artifact(size=package.size_package)
                checksum_type = getattr(CHECKSUM_TYPES, package.checksum_type.upper())
                setattr(artifact, checksum_type, package.pkgId)
                url = urlpath_sanitize(self.remote_url, package.location_href)
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

                packages_pb.increment()
                await self.put(dc)

    async def parse_advisories(self, result):
        """Parse advisories from the remote repository."""
        updateinfo_xml_path = result.path

        updates = await RpmFirstStage.parse_updateinfo(updateinfo_xml_path)
        progress_data = {
            "message": "Parsed Advisories",
            "code": "sync.parsing.advisories",
            "total": len(updates),
        }
        with ProgressReport(**progress_data) as advisories_pb:
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

                advisories_pb.increment()
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

            for declarative_content in batch:
                await self.put(declarative_content)


class RpmContentSaver(ContentSaver):
    """
    A modification of ContentSaver stage that additionally saves RPM plugin specific items.

    Saves UpdateCollection, UpdateCollectionPackage, UpdateReference objects related to
    the UpdateRecord content unit.
    """

    async def _post_save(self, batch):
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
                Addon.objects.bulk_create(addons)
            if checksums:
                Checksum.objects.bulk_create(checksums)
            if images:
                Image.objects.bulk_create(images)
            if variants:
                Variant.objects.bulk_create(variants)

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
            UpdateCollection.objects.bulk_create(update_collection_to_save)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(update_collection_packages_to_save)

        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save)
