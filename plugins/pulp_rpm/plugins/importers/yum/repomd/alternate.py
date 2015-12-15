import os

from threading import Event
from logging import getLogger
from gettext import gettext as _

from nectar.report import DownloadReport

from pulp.server.content.sources.container import ContentContainer, Listener
from pulp.server.content.sources.model import Request

from pulp_rpm.plugins.importers.yum.utils import RepoURLModifier
from pulp_rpm.plugins.importers.yum.repomd.nectar_factory import create_downloader


_log = getLogger(__name__)

CONTAINER_REPORT = _('The content container reported: %(r)s for base URL: %(u)s')


class Packages(object):
    """
    Package downloader.

    :ivar base_url: The repository base url.
    :type base_url: str
    :ivar units: An iterable of units to download.
    :type units: iterable
    :ivar dst_dir: The absolute path to where the packages are to be downloaded.
    :type dst_dir: str
    :ivar listener: A nectar listener.
    :type listener: nectar.listener.DownloadListener
    :ivar primary: The primary nectar downloader.
    :type primary: nectar.downloaders.base.Downloader
    :ivar container: A content container.
    :type container: ContentContainer
    :ivar canceled: An event that signals the running download has been canceled.
    :type canceled: threading.Event
    """

    def __init__(self, base_url, nectar_conf, units, dst_dir, listener, url_modify=None):
        """
        :param base_url: The repository base url.
        :type base_url: str
        :param units: An iterable of units to download.
        :type units: iterable
        :param dst_dir: The absolute path to where the packages are to be downloaded.
        :type dst_dir: str
        :param listener: A nectar listener.
        :type listener: nectar.listener.DownloadListener
        :param url_modify: Optional URL modifier
        :type url_modify: pulp_rpm.plugins.importers.yum.utils.RepoURLModifier
        """
        self.base_url = base_url
        self.units = units
        self.dst_dir = dst_dir
        self.listener = ContainerListener(listener)
        self.primary = create_downloader(base_url, nectar_conf)
        self.container = ContentContainer()
        self.canceled = Event()
        self._url_modify = url_modify or RepoURLModifier()

    @property
    def downloader(self):
        """
        Provided only for API comparability.
        :return: self
        """
        return self

    def get_requests(self):
        """
        Get requests for the units requested to be downloaded.

        :return: An iterable of: Request
        :rtype: iterable
        """
        for unit in self.units:
            base_url = unit.base_url or self.base_url
            url = self._url_modify(base_url, path_append=unit.filename)
            destination = os.path.join(self.dst_dir, unit.filename)
            request = Request(
                type_id=unit._content_type_id,
                unit_key=unit.unit_key,
                url=url,
                destination=destination)
            request.data = unit
            yield request

    def download_packages(self):
        """
        Download packages using alternate content source container.
        """
        report = self.container.download(
            self.canceled, self.primary, self.get_requests(), self.listener)
        _log.info(CONTAINER_REPORT, dict(r=report.dict(), u=self.base_url))

    def cancel(self):
        """
        Cancel a running download.
        """
        self.canceled.set()


class ContainerListener(Listener):
    """
    Provides API mapping between the wrapped content listener
    and the content container listener.
    """

    def __init__(self, content_listener):
        """
        :param content_listener: The wrapped content listener.
        :type content_listener: pulp_rpm.plugins.importers.yum.listener.ContentListener
        """
        Listener.__init__(self)
        self.content_listener = content_listener

    def download_succeeded(self, request):
        """
        Notification that downloading has succeeded for the specified request.
        Fields mapped and forwarded to the wrapped listener.
        :param request: A download request.
        :type request: pulp.server.content.sources.model.Request
        """
        report = DownloadReport(request.url, request.destination, request.data)
        self.content_listener.download_succeeded(report)

    def download_failed(self, request):
        """
        Notification that downloading has failed for the specified request.
        Fields mapped and forwarded to the wrapped listener.
        :param request: A download request.
        :type request: pulp.server.content.sources.model.Request
        """
        report = DownloadReport(request.url, request.destination, request.data)
        report.error_report['errors'] = request.errors
        self.content_listener.download_failed(report)
