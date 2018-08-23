import asyncio
import logging

from gettext import gettext as _  # noqa:F401
from urllib.parse import urljoin

import createrepo_c as cr

from pulpcore.plugin.models import Artifact, ProgressBar, Repository
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage
)

from pulp_rpm.app.constants import CHECKSUM_TYPES, PACKAGE_REPODATA, UPDATE_REPODATA
from pulp_rpm.app.models import RpmContent, RpmRemote, SrpmContent

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

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    log.info(_('Synchronizing: repository={r} remote={p}').format(
        r=repository.name, p=remote.name))

    first_stage = RpmFirstStage(remote)
    DeclarativeVersion(first_stage, repository).create()


class RpmFirstStage(Stage):
    def __init__(self, remote):
        """
        The first stage of a pulp_rpm sync pipeline.

        Args:
            remote (RpmRemote): The remote data to be used when syncing

        """
        self.remote = remote

    async def __call__(self, in_q, out_q):
        """
        Build `DeclarativeContent` from the repodata.

        Args:
            in_q (asyncio.Queue): Unused because the first stage doesn't read from an input queue.
            out_q (asyncio.Queue): The out_q to send `DeclarativeContent` objects to

        """
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

        with ProgressBar(message='Downloading and Parsing Metadata') as pb:
            downloader = self.remote.get_downloader(urljoin(self.remote.url,
                                                            'repodata/repomd.xml'))
            # TODO: decide how to distinguish between a mirror list and a normal repo
            result = await downloader.run()
            pb.increment()

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
                    downloader = self.remote.get_downloader(updateinfo_url)
                    downloaders.append([downloader.run()])
                else:
                    log.info(_('Unknown repodata type: {t}. Skipped.').format(t=record.type))
                    # TODO: skip databases, save unknown types to publish them as-is

            # to preserve order, downloaders are created after all repodata urls are identified
            package_repodata_downloaders = []
            for repodata_type in PACKAGE_REPODATA:
                downloader = self.remote.get_downloader(package_repodata_urls[repodata_type])
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
                        pb.done += 3
                        pb.save()

                        packages = await parse_repodata(primary_xml_path,
                                                        filelists_xml_path,
                                                        other_xml_path)
                        for pkg in packages.values():
                            if SrpmContent.is_srpm(pkg):
                                package = SrpmContent(**SrpmContent.createrepo_to_dict(pkg))
                            else:
                                package = RpmContent(**RpmContent.createrepo_to_dict(pkg))
                            artifact = Artifact(size=package.size_package)
                            checksum_type = getattr(CHECKSUM_TYPES, package.checksum_type.upper())
                            setattr(artifact, checksum_type, package.pkgId)
                            url = urljoin(self.remote.url, package.location_href)
                            da = DeclarativeArtifact(artifact, url, package.location_href,
                                                     self.remote)
                            dc = DeclarativeContent(content=package, d_artifacts=[da])
                            await out_q.put(dc)

                    elif results[0].url == updateinfo_url:
                        updateinfo_xml_path = results[0].path
                        pb.increment()

                        updates = await parse_updateinfo(updateinfo_xml_path)
                        # TODO create updateinfo content

        await out_q.put(None)
