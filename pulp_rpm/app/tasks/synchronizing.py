import asyncio
import gzip
import hashlib
import json
import logging
import os

from collections import defaultdict
from gettext import gettext as _  # noqa:F401
from urllib.parse import urljoin

import createrepo_c as cr
import libcomps

from django.db import transaction

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
    RemoveDuplicates,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents
)

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
from pulp_rpm.app.tasks.utils import (
    get_kickstart_data,
    repodata_exists,
)

from pulp_rpm.app.comps import strdict_to_dict, dict_digest

import gi
gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd as mmdlib  # noqa: E402

log = logging.getLogger(__name__)


def synchronize(remote_pk, repository_pk):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: If the remote does not specify a url to sync.

    """
    remote = RpmRemote.objects.get(pk=remote_pk)
    repository = RpmRepository.objects.get(pk=repository_pk)

    dupe_criteria = [
        {'model': Package, 'field_names': ['name', 'epoch', 'version', 'release', 'arch']},
        {'model': RepoMetadataFile, 'field_names': ['data_type']},
    ]
    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    log.info(_('Synchronizing: repository={r} remote={p}').format(
        r=repository.name, p=remote.name))

    deferred_download = (remote.policy != Remote.IMMEDIATE)  # Interpret download policy

    kickstart = get_kickstart_data(remote)
    if kickstart:
        kickstart["repositories"] = {}
        for repodata in set(kickstart["download"]["repodatas"]):
            if repodata == ".":
                kickstart["repositories"].update({repodata: str(repository_pk)})
                continue
            name = f"{repodata}-{kickstart['hash']}"
            new_repository, created = RpmRepository.objects.get_or_create(
                name=name, plugin_managed=True
            )
            if created:
                new_repository.save()
            kickstart["repositories"].update({repodata: str(new_repository.pk)})
            path = f"{repodata}/"
            new_url = urljoin(remote.url, path)
            if repodata_exists(remote, new_url):
                stage = RpmFirstStage(remote, deferred_download, new_url=new_url)
                dv = RpmDeclarativeVersion(first_stage=stage,
                                           repository=new_repository,
                                           remove_duplicates=dupe_criteria)
                dv.create()

    first_stage = RpmFirstStage(remote, deferred_download, kickstart=kickstart)
    dv = RpmDeclarativeVersion(first_stage=first_stage,
                               repository=repository,
                               remove_duplicates=dupe_criteria)
    dv.create()


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
            RemoteArtifactSaver(),
        ]
        for dupe_query_dict in self.remove_duplicates:
            pipeline.append(RemoveDuplicates(new_version, **dupe_query_dict))

        return pipeline


class RpmFirstStage(Stage):
    """
    First stage of the Asyncio Stage Pipeline.

    Create a :class:`~pulpcore.plugin.stages.DeclarativeContent` object for each content unit
    that should exist in the new :class:`~pulpcore.plugin.models.RepositoryVersion`.
    """

    def __init__(self, remote, deferred_download, new_url=None, kickstart=None):
        """
        The first stage of a pulp_rpm sync pipeline.

        Args:
            remote (RpmRemote): The remote data to be used when syncing
            deferred_download (bool): if True the downloading will not happen now. If False, it will
                happen immediately.

        Keyword Args:
            new_url(str): URL to replace remote url
            kickstart(dict): Kickstart data

        """
        super().__init__()
        self.remote = remote
        self.deferred_download = deferred_download
        self.new_url = new_url
        self.kickstart = kickstart

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
    def hash_update_record(update):
        """
        Find the hex digest for an update record xml from creatrepo_c.

        Args:
            update(createrepo_c.UpdateRecord): update record

        Returns:
            str: a hex digest representing the update record

        """
        uinfo = cr.UpdateInfo()
        uinfo.append(update)
        return hashlib.sha256(uinfo.xml_dump().encode('utf-8')).hexdigest()

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
        packages_pb = ProgressReport(message='Parsed Packages', code='parsing.packages')
        errata_pb = ProgressReport(message='Parsed Erratum', code='parsing.errata')
        modulemd_pb = ProgressReport(message='Parse Modulemd', code='parsing.modulemds')
        modulemd_defaults_pb = ProgressReport(message='Parse Modulemd-defaults',
                                              code='parsing.modulemddefaults')
        comps_pb = ProgressReport(message='Parsed Comps', code='parsing.comps')

        packages_pb.save()
        errata_pb.save()
        comps_pb.save()

        remote_url = self.new_url or self.remote.url
        remote_url = remote_url if remote_url[-1] == "/" else f"{remote_url}/"

        progress_data = dict(message='Downloading Metadata Files', code='downloading.metadata')
        with ProgressReport(**progress_data) as metadata_pb:
            downloader = self.remote.get_downloader(
                url=urljoin(remote_url, 'repodata/repomd.xml')
            )
            # TODO: decide how to distinguish between a mirror list and a normal repo
            result = await downloader.run()
            metadata_pb.increment()

            if self.kickstart:
                d_artifacts = []
                for path, checksum in self.kickstart["download"]["images"].items():
                    artifact = Artifact(**checksum)

                    da = DeclarativeArtifact(
                        artifact=artifact,
                        url=urljoin(remote_url, path),
                        relative_path=path,
                        remote=self.remote,
                        deferred_download=self.deferred_download
                    )

                    d_artifacts.append(da)

                distribution_tree = DistributionTree(**self.kickstart["distribution_tree"])
                dc = DeclarativeContent(content=distribution_tree, d_artifacts=d_artifacts)
                dc.extra_data = self.kickstart
                await self.put(dc)

            repomd_path = result.path
            repomd = cr.Repomd(repomd_path)
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

            for record in repomd.records:
                if record.type in PACKAGE_REPODATA:
                    package_repodata_urls[record.type] = urljoin(remote_url,
                                                                 record.location_href)
                elif record.type in UPDATE_REPODATA:
                    updateinfo_url = urljoin(remote_url, record.location_href)
                    downloader = self.remote.get_downloader(url=updateinfo_url)
                    downloaders.append([downloader.run()])

                elif record.type in COMPS_REPODATA:
                    comps_url = urljoin(remote_url, record.location_href)
                    comps_downloader = self.remote.get_downloader(url=comps_url)

                elif record.type in SKIP_REPODATA:
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

            # we have to sync module.yaml first if it exists, to make relations to packages
            if modulemd_results:
                modulemd_index = mmdlib.ModuleIndex.new()
                open_func = gzip.open if modulemd_results.url.endswith('.gz') else open
                with open_func(modulemd_results.path, 'r') as moduleyaml:
                    modulemd_index.update_from_string(
                        moduleyaml.read().decode(), True
                    )

                modulemd_names = modulemd_index.get_module_names() or []
                modulemd_all = parse_modulemd(modulemd_names, modulemd_index)

                modulemd_pb.total = len(modulemd_all)
                modulemd_pb.state = 'running'
                modulemd_pb.save()

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
                    for artifact in json.loads(dc.content.artifacts):
                        nevra_to_module.setdefault(artifact, set()).add(dc)
                    modulemd_list.append(dc)

                modulemd_default_names = parse_defaults(modulemd_index)

                modulemd_defaults_pb.total = len(modulemd_default_names)
                modulemd_defaults_pb.state = 'running'
                modulemd_defaults_pb.save()

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
                    modulemd_defaults_pb.increment()
                    dc = DeclarativeContent(content=default_content, d_artifacts=[da])
                    await self.put(dc)

            if comps_downloader:
                comps_result = await comps_downloader.run()

                comps = libcomps.Comps()
                comps.fromxml_f(comps_result.path)

                comps_pb.total = (
                    len(comps.groups) + len(comps.categories) + len(comps.environments)
                )
                comps_pb.state = 'running'
                comps_pb.save()

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
                    comps_pb.increment()
                    await self.put(dc_category)

                for dc_environment in dc_environments:
                    comps_pb.increment()
                    await self.put(dc_environment)

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
                    results = downloader.result()
                    if results[0].url == package_repodata_urls['primary']:
                        primary_xml_path = results[0].path
                        filelists_xml_path = results[1].path
                        other_xml_path = results[2].path
                        metadata_pb.done += 3
                        metadata_pb.save()

                        packages = await RpmFirstStage.parse_repodata(primary_xml_path,
                                                                      filelists_xml_path,
                                                                      other_xml_path)
                        packages_pb.total = len(packages)
                        packages_pb.state = 'running'
                        packages_pb.save()

                        for pkg in packages.values():
                            package = Package(**Package.createrepo_to_dict(pkg))
                            artifact = Artifact(size=package.size_package)
                            checksum_type = getattr(CHECKSUM_TYPES, package.checksum_type.upper())
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

                        errata_pb.total = len(updates)
                        errata_pb.state = 'running'
                        errata_pb.save()

                        for update in updates:
                            update_record = UpdateRecord(**UpdateRecord.createrepo_to_dict(update))
                            update_record.digest = RpmFirstStage.hash_update_record(update)
                            future_relations = {'collections': defaultdict(list), 'references': []}

                            for collection in update.collections:
                                coll_dict = UpdateCollection.createrepo_to_dict(collection)
                                coll = UpdateCollection(**coll_dict)

                                for package in collection.packages:
                                    pkg_dict = UpdateCollectionPackage.createrepo_to_dict(package)
                                    pkg = UpdateCollectionPackage(**pkg_dict)
                                    future_relations['collections'][coll].append(pkg)

                            for reference in update.references:
                                reference_dict = UpdateReference.createrepo_to_dict(reference)
                                ref = UpdateReference(**reference_dict)
                                future_relations['references'].append(ref)

                            errata_pb.increment()
                            dc = DeclarativeContent(content=update_record)
                            dc.extra_data = future_relations
                            await self.put(dc)

            # now send modules down the pipeline since all relations have been set up
            for modulemd in modulemd_list:
                modulemd_pb.increment()
                await self.put(modulemd)

            for dc_group in dc_groups:
                comps_pb.increment()
                await self.put(dc_group)

        packages_pb.state = 'completed'
        errata_pb.state = 'completed'
        modulemd_pb.state = 'completed'
        modulemd_defaults_pb.state = 'completed'
        comps_pb.state = 'completed'
        packages_pb.save()
        errata_pb.save()
        modulemd_pb.save()
        modulemd_defaults_pb.save()
        comps_pb.save()


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
            kickstart_data = declarative_content.extra_data

            if kickstart_data["created"] > distribution_tree.pulp_created:
                return

            resources = ["addons", "variants"]
            for resource_name in resources:
                for resource in kickstart_data[resource_name]:
                    key = resource["repository"]
                    del resource["repository"]
                    resource["repository_id"] = kickstart_data["repositories"][key]

            addons = []
            checksums = []
            images = []
            variants = []

            for addon in kickstart_data["addons"]:
                instance = Addon(**addon)
                instance.distribution_tree = distribution_tree
                addons.append(instance)

            for checksum in kickstart_data["checksums"]:
                instance = Checksum(**checksum)
                instance.distribution_tree = distribution_tree
                checksums.append(instance)

            for image in kickstart_data["images"]:
                instance = Image(**image)
                instance.distribution_tree = distribution_tree
                images.append(instance)

            for variant in kickstart_data["variants"]:
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

        update_collections_to_save = []
        update_references_to_save = []
        update_collection_packages_to_save = []

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

                future_relations = declarative_content.extra_data
                update_collections = future_relations.get('collections') or {}
                update_references = future_relations.get('references') or []

                for update_collection, packages in update_collections.items():
                    update_collection.update_record = update_record
                    update_collections_to_save.append(update_collection)
                    for update_collection_package in packages:
                        update_collection_package.update_collection = update_collection
                        update_collection_packages_to_save.append(update_collection_package)

                for update_reference in update_references:
                    update_reference.update_record = update_record
                    update_references_to_save.append(update_reference)

            elif isinstance(declarative_content.content, Modulemd):
                for pkg in declarative_content.extra_data['package_relation']:
                    try:
                        with transaction.atomic():
                            declarative_content.content.packages.add(pkg.content)
                    except ValueError:
                        pass

            elif isinstance(declarative_content.content, PackageCategory):
                for grp in declarative_content.extra_data['packagegroups']:
                    try:
                        with transaction.atomic():
                            declarative_content.content.packagegroups.add(grp.content)
                    except ValueError:
                        pass

            elif isinstance(declarative_content.content, PackageEnvironment):
                for grp in declarative_content.extra_data['packagegroups']:
                    try:
                        with transaction.atomic():
                            declarative_content.content.packagegroups.add(grp.content)
                    except ValueError:
                        pass

                for opt in declarative_content.extra_data['optionalgroups']:
                    try:
                        with transaction.atomic():
                            declarative_content.content.optionalgroups.add(opt.content)
                    except ValueError:
                        pass

            elif isinstance(declarative_content.content, PackageGroup):
                for pkg in declarative_content.extra_data['related_packages']:
                    try:
                        with transaction.atomic():
                            declarative_content.content.related_packages.add(pkg.content)
                    except ValueError:
                        pass

                for packagecategory in declarative_content.extra_data['category_relations']:
                    try:
                        with transaction.atomic():
                            packagecategory.content.packagegroups.add(declarative_content.content)
                    except ValueError:
                        pass

                for packageenvironment in declarative_content.extra_data['environment_relations']:
                    try:
                        with transaction.atomic():
                            packageenvironment.content.packagegroups.add(
                                declarative_content.content)
                    except ValueError:
                        pass

                for packageenvironment in declarative_content.extra_data['env_relations_optional']:
                    try:
                        with transaction.atomic():
                            packageenvironment.content.optionalgroups.add(
                                declarative_content.content)
                    except ValueError:
                        pass

            elif isinstance(declarative_content.content, Package):
                for modulemd in declarative_content.extra_data['modulemd_relation']:
                    try:
                        with transaction.atomic():
                            modulemd.content.packages.add(declarative_content.content)
                    except ValueError:
                        pass

                for packagegroup in declarative_content.extra_data['group_relations']:
                    try:
                        with transaction.atomic():
                            packagegroup.content.related_packages.add(declarative_content.content)
                    except ValueError:
                        pass

        if update_collections_to_save:
            UpdateCollection.objects.bulk_create(update_collections_to_save)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(update_collection_packages_to_save)

        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save)
