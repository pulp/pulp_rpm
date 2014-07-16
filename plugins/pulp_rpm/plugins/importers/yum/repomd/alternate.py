
import os

from threading import Event
from urlparse import urljoin

from nectar.report import DownloadReport

from pulp.server.content.sources import ContentContainer, Listener, Request

from pulp_rpm.plugins.importers.yum.repomd.nectar_factory import create_downloader


class Packages(object):

    def __init__(self, base_url, nectar_conf, units, dst_dir, listener):
        self.base_url = base_url
        self.nectar_conf = nectar_conf
        self.units = units
        self.dst_dir = dst_dir
        self.listener = listener
        self.primary = create_downloader(base_url, nectar_conf)
        self.container = ContentContainer()
        self.canceled = Event()

    def download(self):
        request_list = []
        for unit in self.units:
            url = urljoin(self.base_url, unit.download_path)
            file_name = unit.relative_path.rsplit('/', 1)[-1]
            destination = os.path.join(self.dst_dir, file_name)
            request = Request(
                type_id=unit.TYPE,
                unit_key=unit.unit_key,
                url=url,
                destination=destination)
            request.data = unit
            request_list.append(request)
        listener = AlternateListener(self.listener)
        self.container.download(self.canceled, self.primary, request_list, listener)

    def cancel(self):
        self.canceled.set()


class AlternateListener(Listener):

    def __init__(self, content_listener):
        Listener.__init__(self)
        self.content_listener = content_listener

    def download_succeeded(self, request):
        report = DownloadReport(request.url, request.destination, request.data)
        self.content_listener.download_succeeded(report)

    def download_failed(self, request):
        report = DownloadReport(request.url, request.destination, request.data)
        report.error_report['errors'] = request.errors
        self.content_listener.download_failed(report)