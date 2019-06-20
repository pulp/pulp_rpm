import asyncio
import hashlib
import logging
import os

from collections import defaultdict
from gettext import gettext as _  # noqa:F401
from urllib.parse import urljoin

import createrepo_c as cr

from pulpcore.plugin.models import Artifact, ProgressBar, Remote, Repository

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


from pulp_rpm.app.constants import CHECKSUM_TYPES, PACKAGE_REPODATA, UPDATE_REPODATA
from pulp_rpm.app.models import (
    Package, RpmRemote, UpdateCollection, UpdateCollectionPackage, UpdateRecord, UpdateReference
)

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
    repository = Repository.objects.get(pk=repository_pk)

    package_dupe_criteria = {'model': Package,
                             'field_names': ['name', 'epoch', 'version', 'release', 'arch']}

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    log.info(_('Synchronizing: repository={r} remote={p}').format(
        r=repository.name, p=remote.name))

    deferred_download = (remote.policy != Remote.IMMEDIATE)  # Interpret download policy
    first_stage = RpmFirstStage(remote, deferred_download)
    dv = RpmDeclarativeVersion(first_stage=first_stage,
                               repository=repository,
                               remove_duplicates=[package_dupe_criteria])
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

    def __init__(self, remote, deferred_download):
        """
        The first stage of a pulp_rpm sync pipeline.

        Args:
            remote (RpmRemote): The remote data to be used when syncing
            deferred_download (bool): if True the downloading will not happen now. If False, it will
                happen immediately.

        """
        super().__init__()
        self.remote = remote
        self.deferred_download = deferred_download

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
        packages_pb = ProgressBar(message='Parsed Packages')
        erratum_pb = ProgressBar(message='Parsed Erratum')

        packages_pb.save()
        erratum_pb.save()

        with ProgressBar(message='Downloading Metadata Files') as metadata_pb:
            downloader = self.remote.get_downloader(
                url=urljoin(self.remote.url, 'repodata/repomd.xml')
            )
            # TODO: decide how to distinguish between a mirror list and a normal repo
            result = await downloader.run()
            metadata_pb.increment()

            repomd_path = result.path
            repomd = cr.Repomd(repomd_path)
            package_repodata_urls = {}
            downloaders = []

            for record in repomd.records:
                if record.type in PACKAGE_REPODATA:
                    package_repodata_urls[record.type] = urljoin(self.remote.url,
                                                                 record.location_href)
                elif record.type in UPDATE_REPODATA:
                    updateinfo_url = urljoin(self.remote.url, record.location_href)
                    downloader = self.remote.get_downloader(url=updateinfo_url)
                    downloaders.append([downloader.run()])
                else:
                    log.info(_('Unknown repodata type: {t}. Skipped.').format(t=record.type))
                    # TODO: skip databases, save unknown types to publish them as-is

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
                            url = urljoin(self.remote.url, package.location_href)
                            filename = os.path.basename(package.location_href)
                            da = DeclarativeArtifact(
                                artifact=artifact,
                                url=url,
                                relative_path=filename,
                                remote=self.remote,
                                deferred_download=self.deferred_download
                            )
                            dc = DeclarativeContent(content=package, d_artifacts=[da])
                            packages_pb.increment()
                            await self.put(dc)

                    elif results[0].url == updateinfo_url:
                        updateinfo_xml_path = results[0].path
                        metadata_pb.increment()

                        updates = await RpmFirstStage.parse_updateinfo(updateinfo_xml_path)

                        erratum_pb.total = len(updates)
                        erratum_pb.state = 'running'
                        erratum_pb.save()

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

                            erratum_pb.increment()
                            dc = DeclarativeContent(content=update_record)
                            dc.extra_data = future_relations
                            await self.put(dc)

        packages_pb.state = 'completed'
        erratum_pb.state = 'completed'
        packages_pb.save()
        erratum_pb.save()


class RpmContentSaver(ContentSaver):
    """
    A modification of ContentSaver stage that additionally saves RPM plugin specific items.

    Saves UpdateCollection, UpdateCollectionPackage, UpdateReference objects related to
    the UpdateRecord content unit.
    """

    async def _post_save(self, batch):
        """
        Save a batch of UpdateCollection, UpdateCollectionPackage, UpdateReference objects.

        Args:
            batch (list of :class:`~pulpcore.plugin.stages.DeclarativeContent`): The batch of
                :class:`~pulpcore.plugin.stages.DeclarativeContent` objects to be saved.

        """
        update_collections_to_save = []
        update_references_to_save = []
        update_collection_packages_to_save = []

        for declarative_content in batch:
            if declarative_content is None:
                continue
            if not isinstance(declarative_content.content, UpdateRecord):
                continue
            update_record = declarative_content.content

            relations_exist = update_record.collections.count() or update_record.references.count()
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

        if update_collections_to_save:
            UpdateCollection.objects.bulk_create(update_collections_to_save)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(update_collection_packages_to_save)

        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save)
