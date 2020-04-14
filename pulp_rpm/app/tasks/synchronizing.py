import asyncio
import gzip
import logging
import os

from collections import defaultdict
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


def repodata_exists(remote, url):
    """
    Check if repodata exists.

    """
    downloader = remote.get_downloader(url=urljoin(url, "repodata/repomd.xml"))

    try:
        downloader.fetch()
    except ClientResponseError as exc:
        if 404 == exc.status:
            return False
    except FileNotFoundError:
        return False

    return True


def synchronize(remote_pk, repository_pk, mirror, skip_types, optimize):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (bool): Mirror mode
        skip_types (list): List of content to skip.

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

    treeinfo = get_treeinfo_data(remote)
    if treeinfo:
        treeinfo["repositories"] = {}
        for repodata in set(treeinfo["download"]["repodatas"]):
            if repodata == ".":
                treeinfo["repositories"].update({repodata: str(repository_pk)})
                continue
            name = f"{repodata}-{treeinfo['hash']}"
            sub_repo, created = RpmRepository.objects.get_or_create(
                name=name, sub_repo=True
            )
            if created:
                sub_repo.save()
            treeinfo["repositories"].update({repodata: str(sub_repo.pk)})
            path = f"{repodata}/"
            new_url = urljoin(remote.url, path)
            if repodata_exists(remote, new_url):
                stage = RpmFirstStage(
                    remote,
                    sub_repo,
                    deferred_download,
                    optimize=optimize,
                    skip_types=skip_types,
                    new_url=new_url,
                )
                dv = RpmDeclarativeVersion(first_stage=stage,
                                           repository=sub_repo)
                dv.create()

    first_stage = RpmFirstStage(remote,
                                repository,
                                deferred_download,
                                optimize=optimize,
                                skip_types=skip_types,
                                treeinfo=treeinfo)
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

    def __init__(self, remote, repository, deferred_download, optimize=True, skip_types=[],
                 new_url=None, treeinfo=None):
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
            optimize(bool): Optimize sync

        """
        super().__init__()
        self.remote = remote
        self.repository = repository
        self.deferred_download = deferred_download
        self.new_url = new_url
        self.treeinfo = treeinfo
        self.skip_types = skip_types
        self.optimize = optimize

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
        """
        Build `DeclarativeContent` from the repodata.
        """
        remote_url = self.new_url or self.remote.url
        remote_url = remote_url if remote_url[-1] == "/" else f"{remote_url}/"
        optimize_sync = self.optimize

        progress_data = dict(message='Downloading Metadata Files', code='downloading.metadata')
        with ProgressReport(**progress_data) as metadata_pb:
            downloader = self.remote.get_downloader(
                url=urljoin(remote_url, 'repodata/repomd.xml')
            )
            # TODO: decide how to distinguish between a mirror list and a normal repo
            result = await downloader.run()
            metadata_pb.increment()

            repomd_path = result.path
            repomd = cr.Repomd(repomd_path)

            # Caution: we are not storing when the remote was last updated, so the order of this
            # logic must remain in this order where we first check the version number as other
            # changes than sync could have taken place such that the date or repo version will be
            # different from last sync
            if (
                optimize_sync and
                self.repository.last_sync_remote and
                self.remote.pk == self.repository.last_sync_remote.pk and
                (self.repository.last_sync_repo_version ==
                 self.repository.latest_version().number) and
                (self.remote.pulp_last_updated <=
                 self.repository.latest_version().pulp_created) and
                is_previous_version(repomd.revision, self.repository.last_sync_revision_number)
            ):
                optimize_data = dict(message='Optimizing Sync', code='optimizing.sync')
                with ProgressReport(**optimize_data) as optimize_pb:
                    optimize_pb.done = 1
                    optimize_pb.save()
                    return

            self.repository.last_sync_revision_number = repomd.revision

            if self.treeinfo:
                d_artifacts = [
                    DeclarativeArtifact(
                        artifact=Artifact(),
                        url=urljoin(remote_url, self.treeinfo["filename"]),
                        relative_path=".treeinfo",
                        remote=self.remote,
                        deferred_download=False,
                    )
                ]
                for path, checksum in self.treeinfo["download"]["images"].items():
                    artifact = Artifact(**checksum)
                    da = DeclarativeArtifact(
                        artifact=artifact,
                        url=urljoin(remote_url, path),
                        relative_path=path,
                        remote=self.remote,
                        deferred_download=self.deferred_download
                    )
                    d_artifacts.append(da)

                distribution_tree = DistributionTree(**self.treeinfo["distribution_tree"])
                dc = DeclarativeContent(content=distribution_tree, d_artifacts=d_artifacts)
                dc.extra_data = self.treeinfo
                await self.put(dc)

            package_repodata_urls = {}
            downloaders = []
            modulemd_list = list()
            dc_groups = []
            dc_categories = []
            dc_environments = []
            nevra_to_module = defaultdict(dict)
            pkgname_to_groups = defaultdict(list)
            group_to_categories = defaultdict(list)
            group_to_environments = defaultdict(list)
            optionalgroup_to_environments = defaultdict(list)
            modulemd_results = None
            comps_downloader = None
            main_types = set()
            checksums = {}

            for record in repomd.records:
                checksums[record.type] = record.checksum_type.upper()
                if record.type in PACKAGE_REPODATA:
                    main_types.update([record.type])
                    package_repodata_urls[record.type] = urljoin(remote_url, record.location_href)

                elif record.type in UPDATE_REPODATA:
                    updateinfo_url = urljoin(remote_url, record.location_href)
                    downloader = self.remote.get_downloader(url=updateinfo_url)
                    downloaders.append([downloader.run()])

                elif record.type in COMPS_REPODATA:
                    comps_url = urljoin(remote_url, record.location_href)
                    comps_downloader = self.remote.get_downloader(url=comps_url)

                elif record.type in SKIP_REPODATA:
                    continue

                elif '_zck' in record.type:
                    continue

                elif record.type in MODULAR_REPODATA:
                    modules_url = urljoin(remote_url, record.location_href)
                    modulemd_downloader = self.remote.get_downloader(url=modules_url)
                    modulemd_results = await modulemd_downloader.run()

                elif record.type not in PACKAGE_DB_REPODATA:
                    file_data = {record.checksum_type: record.checksum, "size": record.size}
                    da = DeclarativeArtifact(
                        artifact=Artifact(**file_data),
                        url=urljoin(remote_url, record.location_href),
                        relative_path=record.location_href,
                        remote=self.remote,
                        deferred_download=False
                    )
                    repo_metadata_file = RepoMetadataFile(
                        data_type=record.type,
                        checksum_type=record.checksum_type,
                        checksum=record.checksum,
                    )
                    dc = DeclarativeContent(content=repo_metadata_file, d_artifacts=[da])
                    await self.put(dc)

            missing_type = set(PACKAGE_REPODATA) - main_types
            if missing_type:
                raise FileNotFoundError(_("XML file(s): {filename} not found").format(
                    filename=", ".join(missing_type)))

            self.repository.original_checksum_types = checksums

            # we have to sync module.yaml first if it exists, to make relations to packages
            if modulemd_results:
                modulemd_index = mmdlib.ModuleIndex.new()
                open_func = gzip.open if modulemd_results.url.endswith('.gz') else open
                with open_func(modulemd_results.path, 'r') as moduleyaml:
                    content = moduleyaml.read()
                    module_content = content if isinstance(content, str) else content.decode()
                    modulemd_index.update_from_string(module_content, True)

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
                        url=modules_url
                    )
                    modulemd_content = Modulemd(**modulemd)
                    dc = DeclarativeContent(content=modulemd_content, d_artifacts=[da])
                    dc.extra_data = defaultdict(list)

                    # dc.content.artifacts are Modulemd artifacts
                    for artifact in dc.content.artifacts:
                        nevra_to_module.setdefault(artifact, set()).add(dc)
                    modulemd_list.append(dc)

                # delete list now that we're done with it for memory savings
                del modulemd_all

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
                        url=modules_url
                    )
                    default_content = ModulemdDefaults(**default)
                    dc = DeclarativeContent(content=default_content, d_artifacts=[da])
                    await self.put(dc)

                # delete list now that we're done with it for memory savings
                del modulemd_default_names

            if comps_downloader:
                comps_result = await comps_downloader.run()

                comps = libcomps.Comps()
                comps.fromxml_f(comps_result.path)

                with ProgressReport(message='Parsed Comps', code='parsing.comps') as comps_pb:
                    comps_total = (
                        len(comps.groups) + len(comps.categories) + len(comps.environments)
                    )
                    comps_pb.total = comps_total
                    comps_pb.done = comps_total

                if comps.langpacks:
                    langpack_dict = PackageLangpacks.libcomps_to_dict(comps.langpacks)
                    packagelangpack = PackageLangpacks(
                        matches=strdict_to_dict(comps.langpacks),
                        digest=dict_digest(langpack_dict)
                    )
                    dc = DeclarativeContent(content=packagelangpack)
                    dc.extra_data = defaultdict(list)
                    await self.put(dc)

                if comps.categories:
                    for category in comps.categories:
                        category_dict = PackageCategory.libcomps_to_dict(category)
                        category_dict['digest'] = dict_digest(category_dict)
                        packagecategory = PackageCategory(**category_dict)
                        dc = DeclarativeContent(content=packagecategory)
                        dc.extra_data = defaultdict(list)

                        if packagecategory.group_ids:
                            for group_id in packagecategory.group_ids:
                                group_to_categories[group_id['name']].append(dc)
                        dc_categories.append(dc)

                if comps.environments:
                    for environment in comps.environments:
                        environment_dict = PackageEnvironment.libcomps_to_dict(environment)
                        environment_dict['digest'] = dict_digest(environment_dict)
                        packageenvironment = PackageEnvironment(**environment_dict)
                        dc = DeclarativeContent(content=packageenvironment)
                        dc.extra_data = defaultdict(list)

                        if packageenvironment.option_ids:
                            for option_id in packageenvironment.option_ids:
                                optionalgroup_to_environments[option_id['name']].append(dc)

                        if packageenvironment.group_ids:
                            for group_id in packageenvironment.group_ids:
                                group_to_environments[group_id['name']].append(dc)

                        dc_environments.append(dc)

                if comps.groups:
                    for group in comps.groups:
                        group_dict = PackageGroup.libcomps_to_dict(group)
                        group_dict['digest'] = dict_digest(group_dict)
                        packagegroup = PackageGroup(**group_dict)
                        dc = DeclarativeContent(content=packagegroup)
                        dc.extra_data = defaultdict(list)

                        if packagegroup.packages:
                            for package in packagegroup.packages:
                                pkgname_to_groups[package['name']].append(dc)

                        if dc.content.id in group_to_categories.keys():
                            for dc_category in group_to_categories[dc.content.id]:
                                dc.extra_data['category_relations'].append(dc_category)
                                dc_category.extra_data['packagegroups'].append(dc)

                        if dc.content.id in group_to_environments.keys():
                            for dc_environment in group_to_environments[dc.content.id]:
                                dc.extra_data['environment_relations'].append(dc_environment)
                                dc_environment.extra_data['packagegroups'].append(dc)

                        if dc.content.id in optionalgroup_to_environments.keys():
                            for dc_environment in optionalgroup_to_environments[dc.content.id]:
                                dc.extra_data['env_relations_optional'].append(dc_environment)
                                dc_environment.extra_data['optionalgroups'].append(dc)

                        dc_groups.append(dc)

                for dc_category in dc_categories:
                    await self.put(dc_category)

                for dc_environment in dc_environments:
                    await self.put(dc_environment)

            # delete lists now that we're done with them for memory savings
            del dc_environments
            del dc_categories

            # to preserve order, downloaders are created after all repodata urls are identified
            package_repodata_downloaders = []
            for repodata_type in PACKAGE_REPODATA:
                downloader = self.remote.get_downloader(url=package_repodata_urls[repodata_type])
                package_repodata_downloaders.append(downloader.run())

            downloaders.append(package_repodata_downloaders)

            # asyncio.gather is used to preserve the order of results for package repodata
            pending = [asyncio.gather(*downloaders_group) for downloaders_group in downloaders]

            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for downloader in done:
                    try:
                        results = downloader.result()
                    except ClientResponseError as exc:
                        raise HTTPNotFound(reason=_("File not found: {filename}").format(
                            filename=exc.request_info.url))
                    if results[0].url == package_repodata_urls['primary']:
                        primary_xml_path = results[0].path
                        filelists_xml_path = results[1].path
                        other_xml_path = results[2].path
                        metadata_pb.done += 3
                        metadata_pb.save()

                        packages = await RpmFirstStage.parse_repodata(primary_xml_path,
                                                                      filelists_xml_path,
                                                                      other_xml_path)
                        # skip SRPM if defined
                        if 'srpm' in self.skip_types:
                            packages = {
                                pkgId: pkg for pkgId, pkg in packages.items() if pkg.arch != 'src'
                            }

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
                                url = urljoin(remote_url, package.location_href)
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
                                if dc.content.nevra in nevra_to_module.keys():
                                    dc.content.is_modular = True
                                    for dc_modulemd in nevra_to_module[dc.content.nevra]:
                                        dc.extra_data['modulemd_relation'].append(dc_modulemd)
                                        dc_modulemd.extra_data['package_relation'].append(dc)

                                if dc.content.name in pkgname_to_groups.keys():
                                    for dc_group in pkgname_to_groups[dc.content.name]:
                                        dc.extra_data['group_relations'].append(dc_group)
                                        dc_group.extra_data['related_packages'].append(dc)

                                packages_pb.increment()
                                await self.put(dc)

                    elif results[0].url == updateinfo_url:
                        updateinfo_xml_path = results[0].path
                        metadata_pb.increment()

                        updates = await RpmFirstStage.parse_updateinfo(updateinfo_xml_path)

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

            # now send modules down the pipeline since all relations have been set up
            for modulemd in modulemd_list:
                await self.put(modulemd)

            for dc_group in dc_groups:
                await self.put(dc_group)


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
                PackageGroupPackages = PackageGroup.related_packages.through
                PackageCategoryGroups = PackageCategory.packagegroups.through
                PackageEnvironmentGroups = PackageEnvironment.packagegroups.through
                PackageEnvironmentOptionalGroups = PackageEnvironment.optionalgroups.through

                modulemd_pkgs_to_save = []
                group_pkgs_to_save = []
                category_groups_to_save = []
                env_groups_to_save = []
                env_optgroups_to_save = []

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

                    elif isinstance(d_content.content, PackageCategory):
                        for grp in d_content.extra_data['packagegroups']:
                            if not grp.content._state.adding:
                                category_group = PackageCategoryGroups(
                                    packagegroup_id=grp.content.pk,
                                    packagecategory_id=d_content.content.pk,
                                )
                                category_groups_to_save.append(category_group)

                    elif isinstance(d_content.content, PackageEnvironment):
                        for grp in d_content.extra_data['packagegroups']:
                            if not grp.content._state.adding:
                                env_group = PackageEnvironmentGroups(
                                    packagegroup_id=grp.content.pk,
                                    packageenvironment_id=d_content.content.pk,
                                )
                                env_groups_to_save.append(env_group)

                        for opt in d_content.extra_data['optionalgroups']:
                            if not opt.content._state.adding:
                                env_optgroup = PackageEnvironmentOptionalGroups(
                                    packagegroup_id=opt.content.pk,
                                    packageenvironment_id=d_content.content.pk,
                                )
                                env_optgroups_to_save.append(env_optgroup)

                    elif isinstance(d_content.content, PackageGroup):
                        for pkg in d_content.extra_data['related_packages']:
                            if not pkg.content._state.adding:
                                group_pkg = PackageGroupPackages(
                                    package_id=pkg.content.pk,
                                    packagegroup_id=d_content.content.pk
                                )
                                group_pkgs_to_save.append(group_pkg)

                        for packagecategory in d_content.extra_data['category_relations']:
                            if not packagecategory.content._state.adding:
                                category_group = PackageCategoryGroups(
                                    packagegroup_id=d_content.content.pk,
                                    packagecategory_id=packagecategory.content.pk,
                                )
                                category_groups_to_save.append(category_group)

                        for packageenvironment in d_content.extra_data['environment_relations']:
                            if not packageenvironment.content._state.adding:
                                env_group = PackageEnvironmentGroups(
                                    packagegroup_id=d_content.content.pk,
                                    packageenvironment_id=packageenvironment.content.pk,
                                )
                                env_groups_to_save.append(env_group)

                        for packageenvironment in d_content.extra_data['env_relations_optional']:
                            if not packageenvironment.content._state.adding:
                                env_optgroup = PackageEnvironmentOptionalGroups(
                                    packagegroup_id=d_content.content.pk,
                                    packageenvironment_id=packageenvironment.content.pk,
                                )
                                env_optgroups_to_save.append(env_optgroup)

                    elif isinstance(d_content.content, Package):
                        for modulemd in d_content.extra_data['modulemd_relation']:
                            if not modulemd.content._state.adding:
                                module_package = ModulemdPackages(
                                    package_id=d_content.content.pk,
                                    modulemd_id=modulemd.content.pk,
                                )
                                modulemd_pkgs_to_save.append(module_package)

                        for packagegroup in d_content.extra_data['group_relations']:
                            if not packagegroup.content._state.adding:
                                group_pkg = PackageGroupPackages(
                                    package_id=d_content.content.pk,
                                    packagegroup_id=packagegroup.content.pk,
                                )
                                group_pkgs_to_save.append(group_pkg)

                if modulemd_pkgs_to_save:
                    ModulemdPackages.objects.bulk_create(modulemd_pkgs_to_save,
                                                         ignore_conflicts=True)

                if group_pkgs_to_save:
                    PackageGroupPackages.objects.bulk_create(group_pkgs_to_save,
                                                             ignore_conflicts=True)

                if category_groups_to_save:
                    PackageCategoryGroups.objects.bulk_create(
                        category_groups_to_save, ignore_conflicts=True
                    )

                if env_groups_to_save:
                    PackageEnvironmentGroups.objects.bulk_create(env_groups_to_save,
                                                                 ignore_conflicts=True)

                if env_optgroups_to_save:
                    PackageEnvironmentOptionalGroups.objects.bulk_create(
                        env_optgroups_to_save, ignore_conflicts=True
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
                for resource in treeinfo_data[resource_name]:
                    key = resource["repository"]
                    del resource["repository"]
                    resource["repository_id"] = treeinfo_data["repositories"][key]

            addons = []
            checksums = []
            images = []
            variants = []

            for addon in treeinfo_data["addons"]:
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

            for variant in treeinfo_data["variants"]:
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

        UpdateRecordCollections = UpdateRecord.collections.through

        update_collection_to_save = []
        update_record_collections_to_save = []
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
                    update_collection_to_save.append(update_collection)
                    update_record_collections_to_save.append(UpdateRecordCollections(
                        updaterecord=update_record, updatecollection=update_collection
                    ))
                    for update_collection_package in packages:
                        update_collection_package.update_collection = update_collection
                        update_collection_packages_to_save.append(update_collection_package)

                for update_reference in update_references:
                    update_reference.update_record = update_record
                    update_references_to_save.append(update_reference)

        if update_collection_to_save:
            UpdateCollection.objects.bulk_create(update_collection_to_save)

        if update_record_collections_to_save:
            # Saving UpdateRecord -> UpdateCollection relations
            UpdateRecordCollections.objects.bulk_create(update_record_collections_to_save)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(update_collection_packages_to_save)

        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save)
