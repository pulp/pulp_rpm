import asyncio
import gzip
import logging
import os
import re

from collections import defaultdict
from functools import partial
from gettext import gettext as _  # noqa:F401
from urllib.parse import urljoin

from django.db import transaction

from aiohttp.client_exceptions import ClientResponseError
from aiohttp.web_exceptions import HTTPNotFound
import createrepo_c as cr
import libcomps

from pulpcore.plugin.models import (
    Artifact,
    ProgressReport,
    Remote,
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
    QueryExistingContents
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
    SKIP_REPODATA,
    UPDATE_REPODATA
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
    RpmRemote,
    RpmRepository,
    UpdateCollection,
    UpdateCollectionPackage,
    UpdateRecord,
    UpdateReference,
)
from pulp_rpm.app.modulemd import (
    parse_defaults,
    parse_modulemd,
)
from pulp_rpm.app.kickstart.treeinfo import get_treeinfo_data

from pulp_rpm.app.comps import strdict_to_dict, dict_digest
from pulp_rpm.app.shared_utils import is_previous_version

import gi
gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd as mmdlib  # noqa: E402

log = logging.getLogger(__name__)


def get_repomd_file(remote, url):
    """
    Check if repodata exists.

    Args:
        remote(RpmRemote): An RpmRemote to download with.
        url(str): A remote repository URL

    Returns:
        pulpcore.plugin.download.DownloadResult: downloaded repomd.xml

    """
    downloader = remote.get_downloader(url=urljoin(url, "repodata/repomd.xml"))

    try:
        result = downloader.fetch()
    except ClientResponseError as exc:
        if 404 == exc.status:
            return
    except FileNotFoundError:
        return

    return result


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
            repodata_exists = get_repomd_file(remote, match.group(2))
            if match and repodata_exists:
                return match.group(2)

    return None


def fetch_remote_url(remote):
    """Fetch a single remote from which can be content synced."""
    remote_url = remote.url.rstrip("/") + "/"
    downloader = remote.get_downloader(url=urljoin(remote_url, "repodata/repomd.xml"))
    try:
        downloader.fetch()
    except (ClientResponseError, FileNotFoundError):
        return fetch_mirror(remote)
    else:
        return remote_url


def is_optimized_sync(repository, remote, url):
    """
    Check whether it is possible to optimize the synchronization or not.

    Caution: we are not storing when the remote was last updated, so the order of this
    logic must remain in this order where we first check the version number as other
    changes than sync could have taken place such that the date or repo version will be
    different from last sync.

    Args:
        repository(RpmRepository): An RpmRepository to check optimization for.
        remote(RpmRemote): An RPMRemote to check optimization for.
        url(str): A remote repository URL.

    Returns:
        bool: True, if sync is optimized; False, otherwise.

    """
    result = get_repomd_file(remote, url)
    if not result:
        return False

    repomd_path = result.path
    repomd = cr.Repomd(repomd_path)
    is_optimized = (
        repository.last_sync_remote and
        remote.pk == repository.last_sync_remote.pk and
        repository.last_sync_repo_version == repository.latest_version().number and
        remote.pulp_last_updated <= repository.latest_version().pulp_created and
        is_previous_version(repomd.revision, repository.last_sync_revision_number)
    )
    if is_optimized:
        optimize_data = dict(message='Optimizing Sync', code='optimizing.sync')
        with ProgressReport(**optimize_data) as optimize_pb:
            optimize_pb.done = 1
            optimize_pb.save()

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
    remote = RpmRemote.objects.get(pk=remote_pk)
    repository = RpmRepository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    log.info(_('Synchronizing: repository={r} remote={p}').format(
        r=repository.name, p=remote.name))

    deferred_download = (remote.policy != Remote.IMMEDIATE)  # Interpret download policy

    remote_url = fetch_remote_url(remote)
    if not remote_url:
        raise ValueError(_("A no valid remote URL was provided."))
    else:
        remote_url = remote_url.rstrip("/") + "/"

    if optimize and is_optimized_sync(repository, remote, remote_url):
        return

    treeinfo = get_treeinfo_data(remote, remote_url)
    if treeinfo:
        treeinfo["repositories"] = {}
        for repodata in set(treeinfo["download"]["repodatas"]):
            if repodata == DIST_TREE_MAIN_REPO_PATH:
                treeinfo["repositories"].update({repodata: None})
                continue
            name = f"{repodata}-{treeinfo['hash']}"
            sub_repo, created = RpmRepository.objects.get_or_create(
                name=name, sub_repo=True
            )
            if created:
                sub_repo.save()
            directory = treeinfo["repo_map"][repodata]
            treeinfo["repositories"].update({directory: str(sub_repo.pk)})
            path = f"{repodata}/"
            new_url = urljoin(remote_url, path)
            repodata_exists = get_repomd_file(remote, new_url)
            if repodata_exists:
                if optimize and is_optimized_sync(sub_repo, remote, new_url):
                    continue
                stage = RpmFirstStage(
                    remote,
                    sub_repo,
                    deferred_download,
                    skip_types=skip_types,
                    new_url=new_url,
                )
                dv = RpmDeclarativeVersion(first_stage=stage,
                                           repository=sub_repo)
                dv.create()
                sub_repo.last_sync_remote = remote
                sub_repo.last_sync_repo_version = sub_repo.latest_version().number
                sub_repo.save()

    first_stage = RpmFirstStage(remote,
                                repository,
                                deferred_download,
                                skip_types=skip_types,
                                treeinfo=treeinfo,
                                new_url=remote_url)
    dv = RpmDeclarativeVersion(first_stage=first_stage,
                               repository=repository,
                               mirror=mirror)
    dv.create()
    repository.last_sync_remote = remote
    repository.last_sync_repo_version = repository.latest_version().number
    repository.save()


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

    def __init__(self, remote, repository, deferred_download, skip_types=None, new_url=None,
                 treeinfo=None):
        """
        The first stage of a pulp_rpm sync pipeline.

        Args:
            remote (RpmRemote): The remote data to be used when syncing
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
        self.new_url = new_url
        self.treeinfo = treeinfo
        self.skip_types = [] if skip_types is None else skip_types

        self.data = FirstStageData()

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

        packages = {}

        # TODO: handle parsing errors/warnings, warningcb callback can be used below
        cr.xml_parse_primary(primary_xml_path, pkgcb=pkgcb, do_files=False)
        cr.xml_parse_filelists(filelists_xml_path, newpkgcb=newpkgcb)
        cr.xml_parse_other(other_xml_path, newpkgcb=newpkgcb)
        return packages

    async def run(self):
        """Build `DeclarativeContent` from the repodata."""
        self.data.remote_url = self.new_url or self.remote.url

        progress_data = dict(message='Downloading Metadata Files', code='downloading.metadata')
        with ProgressReport(**progress_data) as metadata_pb:
            self.data.metadata_pb = metadata_pb

            downloader = self.remote.get_downloader(
                url=urljoin(self.data.remote_url, 'repodata/repomd.xml')
            )
            result = await downloader.run()
            metadata_pb.increment()

            repomd_path = result.path
            self.data.repomd = cr.Repomd(repomd_path)

            self.repository.last_sync_revision_number = self.data.repomd.revision

            await self.parse_distribution_tree()
            await self.parse_repository_metadata()
            await self.parse_modules_metadata()
            await self.parse_packages_components()
            await self.parse_content()

            # now send modules down the pipeline since all relations have been set up
            for modulemd in self.data.modulemd_list:
                await self.put(modulemd)

            for dc_group in self.data.dc_groups:
                await self.put(dc_group)

    async def parse_distribution_tree(self):
        """Parse content from the file treeinfo if present."""
        if self.treeinfo:
            d_artifacts = [
                DeclarativeArtifact(
                    artifact=Artifact(),
                    url=urljoin(self.data.remote_url, self.treeinfo["filename"]),
                    relative_path=".treeinfo",
                    remote=self.remote,
                    deferred_download=False,
                )
            ]
            for path, checksum in self.treeinfo["download"]["images"].items():
                artifact = Artifact(**checksum)
                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=urljoin(self.data.remote_url, path),
                    relative_path=path,
                    remote=self.remote,
                    deferred_download=self.deferred_download
                )
                d_artifacts.append(da)

            distribution_tree = DistributionTree(**self.treeinfo["distribution_tree"])
            dc = DeclarativeContent(content=distribution_tree, d_artifacts=d_artifacts)
            dc.extra_data = self.treeinfo
            await self.put(dc)

    async def parse_repository_metadata(self):
        """Parse repository metadata from repomd.xml."""
        repository_metadata_parser = RepositoryMetadataParser(self.data, self.remote)
        repository_metadata_parser.parse()

        if repository_metadata_parser.modulemd_downloader:
            self.data.modulemd_results = await repository_metadata_parser.modulemd_downloader.run()
        if repository_metadata_parser.repomd_dcs:
            for dc in repository_metadata_parser.repomd_dcs:
                await self.put(dc)

        self.repository.original_checksum_types = repository_metadata_parser.checksum_types

    async def parse_modules_metadata(self):
        """Parse modules' metadata which define what packages are built for specific releases."""
        modules_metadata_parser = ModulesMetadataParser(self.data)
        modules_metadata_parser.parse()

        if modules_metadata_parser.default_content_dcs:
            for default_content_dc in modules_metadata_parser.default_content_dcs:
                await self.put(default_content_dc)

    async def parse_packages_components(self):
        """Parse packages' components that define how are the packages bundled."""
        if self.data.comps_downloader:
            comps_result = await self.data.comps_downloader.run()
            packages_components_parser = PackagesComponentsParser(self.data, comps_result)
            packages_components_parser.parse()

            if packages_components_parser.package_language_pack_dc:
                await self.put(packages_components_parser.package_language_pack_dc)

            for dc_category in packages_components_parser.dc_categories:
                await self.put(dc_category)

            for dc_environment in packages_components_parser.dc_environments:
                await self.put(dc_environment)

            # delete lists now that we're done with them for memory savings
            del packages_components_parser.dc_environments
            del packages_components_parser.dc_categories

    async def parse_content(self):
        """Download and parse packages' content from the remote repository."""
        # to preserve order, downloaders are created after all repodata urls are identified
        package_repodata_downloaders = []
        for repodata_type in PACKAGE_REPODATA:
            downloader = self.remote.get_downloader(
                url=self.data.package_repodata_urls[repodata_type]
            )
            package_repodata_downloaders.append(downloader.run())

        self.data.downloaders.append(package_repodata_downloaders)

        # asyncio.gather is used to preserve the order of results for package repodata
        pending = [
            asyncio.gather(*downloaders_group) for downloaders_group in self.data.downloaders
        ]
        data_type_handlers = defaultdict(
            lambda: partial(asyncio.sleep, 0), {
                self.data.package_repodata_urls['primary']: self.parse_packages,
                self.data.updateinfo_url: self.parse_advisories
            }
        )

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for downloader in done:
                try:
                    results = downloader.result()
                except ClientResponseError as exc:
                    raise HTTPNotFound(reason=_(f"File not found: {exc.request_info.url}"))
                else:
                    data_url = results[0].url
                    await data_type_handlers[data_url](results)

    async def parse_packages(self, results):
        """Parse packages from the remote repository."""
        primary_xml_path = results[0].path
        filelists_xml_path = results[1].path
        other_xml_path = results[2].path

        self.data.metadata_pb.done += 3
        self.data.metadata_pb.save()

        packages = await RpmFirstStage.parse_repodata(
            primary_xml_path, filelists_xml_path, other_xml_path
        )

        # skip SRPM if defined
        if 'srpm' in self.skip_types:
            packages = {pkgId: pkg for pkgId, pkg in packages.items() if pkg.arch != 'src'}

        await self._parse_packages(packages)

    async def parse_advisories(self, results):
        """Parse advisories from the remote repository."""
        updateinfo_xml_path = results[0].path

        self.data.metadata_pb.increment()

        updates = await RpmFirstStage.parse_updateinfo(updateinfo_xml_path)
        await self._parse_advisories(updates)

    async def _parse_packages(self, packages):
        progress_data = {
            'message': 'Parsed Packages',
            'code': 'parsing.packages',
            'total': len(packages),
        }

        with ProgressReport(**progress_data) as packages_pb:
            for pkg in packages.values():
                package = Package(**Package.createrepo_to_dict(pkg))
                artifact = Artifact(size=package.size_package)
                checksum_type = getattr(
                    CHECKSUM_TYPES, package.checksum_type.upper()
                )
                setattr(artifact, checksum_type, package.pkgId)
                url = urljoin(self.data.remote_url, package.location_href)
                filename = os.path.basename(package.location_href)
                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=url,
                    relative_path=filename,
                    remote=self.remote,
                    deferred_download=self.deferred_download
                )
                dc = DeclarativeContent(content=package, d_artifacts=[da])
                dc.extra_data = defaultdict(list)

                # find if a package relates to a modulemd
                if dc.content.nevra in self.data.nevra_to_module.keys():
                    dc.content.is_modular = True
                    for dc_modulemd in self.data.nevra_to_module[dc.content.nevra]:
                        dc.extra_data['modulemd_relation'].append(dc_modulemd)
                        dc_modulemd.extra_data['package_relation'].append(dc)

                if dc.content.name in self.data.pkgname_to_groups.keys():
                    for dc_group in self.data.pkgname_to_groups[dc.content.name]:
                        dc.extra_data['group_relations'].append(dc_group)
                        dc_group.extra_data['related_packages'].append(dc)

                packages_pb.increment()
                await self.put(dc)

    async def _parse_advisories(self, updates):
        progress_data = {
            'message': 'Parsed Advisories',
            'code': 'parsing.advisories',
            'total': len(updates),
        }
        with ProgressReport(**progress_data) as advisories_pb:
            for update in updates:
                update_record = UpdateRecord(
                    **UpdateRecord.createrepo_to_dict(update)
                )
                update_record.digest = hash_update_record(update)
                future_relations = {
                    'collections': defaultdict(list), 'references': []
                }

                for collection in update.collections:
                    coll_dict = UpdateCollection.createrepo_to_dict(collection)
                    coll = UpdateCollection(**coll_dict)

                    for package in collection.packages:
                        pkg_dict = UpdateCollectionPackage.createrepo_to_dict(
                            package
                        )
                        pkg = UpdateCollectionPackage(**pkg_dict)
                        future_relations['collections'][coll].append(pkg)

                for reference in update.references:
                    reference_dict = UpdateReference.createrepo_to_dict(reference)
                    ref = UpdateReference(**reference_dict)
                    future_relations['references'].append(ref)

                advisories_pb.increment()
                dc = DeclarativeContent(content=update_record)
                dc.extra_data = future_relations
                await self.put(dc)


class FirstStageData:
    """A data class that holds data required for synchronization.

    The stored data are passed between multiple worker classes and are altered during
    the synchronization process.
    """

    def __init__(self):
        """Store shared data which are going to be used by parsers."""
        self.repomd = None
        self.remote_url = None
        self.metadata_pb = None

        self.package_repodata_urls = {}
        self.downloaders = []

        self.nevra_to_module = defaultdict(dict)
        self.pkgname_to_groups = defaultdict(list)
        self.modulemd_results = None
        self.comps_downloader = None

        self.modules_url = None
        self.updateinfo_url = None

        self.modulemd_list = []
        self.dc_groups = []


class RepositoryMetadataParser:
    """A class used for parsing repository metadata (repomd)."""

    def __init__(self, data, remote):
        """Store the data class, the passed remote, and initialize class variables."""
        self.data = data
        self.remote = remote

        self.main_types = set()
        self.checksum_types = {}
        self.modulemd_downloader = None
        self.repomd_dcs = []

    def parse(self):
        """Parse repository metadata."""
        record_types_op = defaultdict(lambda: self._set_repomd_file)

        record_types_op.update(dict.fromkeys(PACKAGE_REPODATA, self._update_repodata_urls))
        record_types_op.update(dict.fromkeys(UPDATE_REPODATA, self._append_downloader))
        record_types_op.update(dict.fromkeys(COMPS_REPODATA, self._set_comps_downloader))
        record_types_op.update(dict.fromkeys(MODULAR_REPODATA, self._get_modulemd_results))
        record_types_op.update(dict.fromkeys(SKIP_REPODATA, lambda _: None))

        for record in self.data.repomd.records:
            self.checksum_types[record.type] = record.checksum_type.upper()
            record_types_op[record.type](record)

        missing_types = set(PACKAGE_REPODATA) - self.main_types
        if missing_types:
            raise FileNotFoundError(
                _("XML file(s): {filenames} not found").format(filenames=", ".join(missing_types))
            )

    def _update_repodata_urls(self, record):
        self.main_types.update([record.type])
        repodata_url = urljoin(self.data.remote_url, record.location_href)
        self.data.package_repodata_urls[record.type] = repodata_url

    def _append_downloader(self, record):
        self.data.updateinfo_url = urljoin(self.data.remote_url, record.location_href)
        downloader = self.remote.get_downloader(url=self.data.updateinfo_url)
        self.data.downloaders.append([downloader.run()])

    def _set_comps_downloader(self, record):
        comps_url = urljoin(self.data.remote_url, record.location_href)
        self.data.comps_downloader = self.remote.get_downloader(url=comps_url)

    def _get_modulemd_results(self, record):
        self.data.modules_url = urljoin(self.data.remote_url, record.location_href)
        self.modulemd_downloader = self.remote.get_downloader(url=self.data.modules_url)

    def _set_repomd_file(self, record):
        if '_zck' not in record.type and record.type not in PACKAGE_DB_REPODATA:
            file_data = {record.checksum_type: record.checksum, "size": record.size}
            da = DeclarativeArtifact(
                artifact=Artifact(**file_data),
                url=urljoin(self.data.remote_url, record.location_href),
                relative_path=record.location_href,
                remote=self.remote,
                deferred_download=False
            )
            repo_metadata_file = RepoMetadataFile(
                data_type=record.type,
                checksum_type=record.checksum_type,
                checksum=record.checksum,
                relative_path=record.location_href
            )
            dc = DeclarativeContent(content=repo_metadata_file, d_artifacts=[da])
            self.repomd_dcs.append(dc)


class ModulesMetadataParser:
    """A class used for parsing modules' metadata (modulemd)."""

    def __init__(self, data):
        """Store the data class and initialize a list of default contents' declarative contents."""
        self.data = data

        self.default_content_dcs = []

    def parse(self):
        """Parse module.yaml, if exists, to create relations between packages."""
        if self.data.modulemd_results:
            modulemd_index = mmdlib.ModuleIndex.new()
            open_func = gzip.open if self.data.modulemd_results.url.endswith('.gz') else open
            with open_func(self.data.modulemd_results.path, 'r') as moduleyaml:
                content = moduleyaml.read()
                module_content = content if isinstance(content, str) else content.decode()
                modulemd_index.update_from_string(module_content, True)

            self._parse_modulemd_list(modulemd_index)
            self._parse_modulemd_default_names(modulemd_index)

    def _parse_modulemd_list(self, modulemd_index):
        modulemd_names = modulemd_index.get_module_names() or []
        modulemd_all = parse_modulemd(modulemd_names, modulemd_index)

        # Parsing modules happens all at one time, and from here on no useful work happens.
        # So just report that it finished this stage.
        modulemd_pb_data = {'message': 'Parsed Modulemd', 'code': 'parsing.modulemds'}
        with ProgressReport(**modulemd_pb_data) as modulemd_pb:
            modulemd_total = len(modulemd_all)
            modulemd_pb.total = modulemd_total
            modulemd_pb.done = modulemd_total

        for modulemd in modulemd_all:
            artifact = modulemd.pop('artifact')
            relative_path = '{}{}{}{}{}snippet'.format(
                modulemd[PULP_MODULE_ATTR.NAME], modulemd[PULP_MODULE_ATTR.STREAM],
                modulemd[PULP_MODULE_ATTR.VERSION], modulemd[PULP_MODULE_ATTR.CONTEXT],
                modulemd[PULP_MODULE_ATTR.ARCH]
            )
            da = DeclarativeArtifact(
                artifact=artifact,
                relative_path=relative_path,
                url=self.data.modules_url
            )
            modulemd_content = Modulemd(**modulemd)
            dc = DeclarativeContent(content=modulemd_content, d_artifacts=[da])
            dc.extra_data = defaultdict(list)

            # dc.content.artifacts are Modulemd artifacts
            for artifact in dc.content.artifacts:
                self.data.nevra_to_module.setdefault(artifact, set()).add(dc)
            self.data.modulemd_list.append(dc)

        # delete list now that we're done with it for memory savings
        del modulemd_all

    def _parse_modulemd_default_names(self, modulemd_index):
        modulemd_default_names = parse_defaults(modulemd_index)

        # Parsing module-defaults happens all at one time, and from here on no useful
        # work happens. So just report that it finished this stage.
        modulemd_defaults_pb_data = {
            'message': 'Parsed Modulemd-defaults', 'code': 'parsing.modulemd_defaults'
        }
        with ProgressReport(**modulemd_defaults_pb_data) as modulemd_defaults_pb:
            modulemd_defaults_total = len(modulemd_default_names)
            modulemd_defaults_pb.total = modulemd_defaults_total
            modulemd_defaults_pb.done = modulemd_defaults_total

        for default in modulemd_default_names:
            artifact = default.pop('artifact')
            relative_path = '{}{}snippet'.format(
                default[PULP_MODULEDEFAULTS_ATTR.MODULE],
                default[PULP_MODULEDEFAULTS_ATTR.STREAM]
            )
            da = DeclarativeArtifact(
                artifact=artifact,
                relative_path=relative_path,
                url=self.data.modules_url
            )
            default_content = ModulemdDefaults(**default)
            self.default_content_dcs.append(
                DeclarativeContent(content=default_content, d_artifacts=[da])
            )

        # delete list now that we're done with it for memory savings
        del modulemd_default_names


class PackagesComponentsParser:
    """A class used for parsing packages' components (comps)."""

    def __init__(self, data, comps_result):
        """Store the data class and initialize structures required for parsing."""
        self.data = data
        self.comps_result = comps_result

        self.group_to_categories = defaultdict(list)

        self.group_to_environments = defaultdict(list)
        self.optionalgroup_to_environments = defaultdict(list)

        self.package_language_pack_dc = None
        self.dc_categories = []
        self.dc_environments = []

    def parse(self):
        """Parse packages' components."""
        comps = libcomps.Comps()
        comps.fromxml_f(self.comps_result.path)

        with ProgressReport(message='Parsed Comps', code='parsing.comps') as comps_pb:
            comps_total = (len(comps.groups) + len(comps.categories) + len(comps.environments))
            comps_pb.total = comps_total
            comps_pb.done = comps_total

        if comps.langpacks:
            langpack_dict = PackageLangpacks.libcomps_to_dict(comps.langpacks)
            packagelangpack = PackageLangpacks(
                matches=strdict_to_dict(comps.langpacks),
                digest=dict_digest(langpack_dict)
            )
            self.package_language_pack_dc = DeclarativeContent(content=packagelangpack)
            self.package_language_pack_dc.extra_data = defaultdict(list)

        self._init_dc_categories(comps)
        self._init_dc_environments(comps)
        self._init_dc_groups(comps)

    def _init_dc_categories(self, comps):
        if comps.categories:
            for category in comps.categories:
                category_dict = PackageCategory.libcomps_to_dict(category)
                category_dict['digest'] = dict_digest(category_dict)
                packagecategory = PackageCategory(**category_dict)
                dc = DeclarativeContent(content=packagecategory)
                dc.extra_data = defaultdict(list)

                if packagecategory.group_ids:
                    for group_id in packagecategory.group_ids:
                        self.group_to_categories[group_id['name']].append(dc)
                self.dc_categories.append(dc)

    def _init_dc_environments(self, comps):
        if comps.environments:
            for environment in comps.environments:
                environment_dict = PackageEnvironment.libcomps_to_dict(environment)
                environment_dict['digest'] = dict_digest(environment_dict)
                packageenvironment = PackageEnvironment(**environment_dict)
                dc = DeclarativeContent(content=packageenvironment)
                dc.extra_data = defaultdict(list)

                if packageenvironment.option_ids:
                    for option_id in packageenvironment.option_ids:
                        self.optionalgroup_to_environments[option_id['name']].append(dc)

                if packageenvironment.group_ids:
                    for group_id in packageenvironment.group_ids:
                        self.group_to_environments[group_id['name']].append(dc)

                self.dc_environments.append(dc)

    def _init_dc_groups(self, comps):
        if comps.groups:
            for group in comps.groups:
                group_dict = PackageGroup.libcomps_to_dict(group)
                group_dict['digest'] = dict_digest(group_dict)
                packagegroup = PackageGroup(**group_dict)
                dc = DeclarativeContent(content=packagegroup)
                dc.extra_data = defaultdict(list)

                if packagegroup.packages:
                    for package in packagegroup.packages:
                        self.data.pkgname_to_groups[package['name']].append(dc)

                if dc.content.id in self.group_to_categories.keys():
                    for dc_category in self.group_to_categories[dc.content.id]:
                        dc.extra_data['category_relations'].append(dc_category)
                        dc_category.extra_data['packagegroups'].append(dc)

                if dc.content.id in self.group_to_environments.keys():
                    for dc_environment in self.group_to_environments[dc.content.id]:
                        dc.extra_data['environment_relations'].append(dc_environment)
                        dc_environment.extra_data['packagegroups'].append(dc)

                if dc.content.id in self.optionalgroup_to_environments.keys():
                    for dc_environment in self.optionalgroup_to_environments[dc.content.id]:
                        dc.extra_data['env_relations_optional'].append(dc_environment)
                        dc_environment.extra_data['optionalgroups'].append(dc)

                self.data.dc_groups.append(dc)


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
                        for pkg in d_content.extra_data['package_relation']:
                            if not pkg.content._state.adding:
                                module_package = ModulemdPackages(
                                    package_id=pkg.content.pk,
                                    modulemd_id=d_content.content.pk,
                                )
                                modulemd_pkgs_to_save.append(module_package)

                    elif isinstance(d_content.content, Package):
                        for modulemd in d_content.extra_data['modulemd_relation']:
                            if not modulemd.content._state.adding:
                                module_package = ModulemdPackages(
                                    package_id=d_content.content.pk,
                                    modulemd_id=modulemd.content.pk,
                                )
                                modulemd_pkgs_to_save.append(module_package)

                if modulemd_pkgs_to_save:
                    ModulemdPackages.objects.bulk_create(modulemd_pkgs_to_save,
                                                         ignore_conflicts=True)

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
                update_collections = future_relations.get('collections', {})
                update_references = future_relations.get('references', [])

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
