# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
from urlparse import urljoin

from pulp.common.download.downloaders.curl import HTTPSCurlDownloader
from pulp.common.download.config import DownloaderConfig
from pulp.common.download.request import DownloadRequest


class Packages(object):
    """
    Stateful downloader for a Yum repository's packages.

    Given an iterator of package information dictionaries, download the packages
    to a given destination directory.

    :ivar repo_url: Yum repository's URL
    :ivar packages_information_iterator: iterator of package information dictionaries
    :ivar dst_dir: Directory to store downloaded packages in
    :ivar event_listener: pulp.common.download.listener.DownloadEventListener instance
    :ivar downloader: pulp.common.download.backends.base.DownloadBackend instance
    """

    def __init__(self, repo_url, packages_information_iterator, dst_dir, event_listener=None):
        self.repo_url = repo_url
        self.packages_information_iterator = packages_information_iterator
        self.dst_dir = dst_dir

        downloader_config = DownloaderConfig()
        self.downloader = HTTPSCurlDownloader(downloader_config, event_listener)

    def download_packages(self):
        """
        Download the repository's packages to the destination directory.
        """
        self.downloader.download(self._request_generator())

    def _request_generator(self):
        """
        Request generator to convert package information dictionaries to
        download request on demand.

        :return: download request generator
        :rtype: generator
        """
        for package_info in self.packages_information_iterator:
            url = urljoin(self.repo_url, package_info['relative_url_path'])

            file_name = package_info['relative_url_path'].rsplit('/', 1)[-1]
            destination = os.path.join(self.dst_dir, file_name)

            request = DownloadRequest(url, destination, package_info)
            yield request

