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
from tempfile import mkdtemp

from pulp.common.download import factory as download_factory
from pulp.common.download.config import DownloaderConfig
from pulp.common.download.listener import DownloadEventListener
from pulp.common.download.request import DownloadRequest
from pulp.server.compat import ObjectId


class Packages(object):

    def __init__(self, repo_url, primary_packages_iter, dst_dir=None):
        self.repo_url = repo_url
        self.primary_packages_iter = primary_packages_iter
        self.dst_dir = dst_dir or mkdtemp()

        downloader_config = DownloaderConfig(protocol='https', max_concurrent=20)
        event_listener = PackagesDownloadEventListener()
        self.downloader = download_factory.get_downloader(downloader_config, event_listener)

    def download_packages(self):
        download_request_list = []

        for package_info in self.primary_packages_iter:
            # TODO logic/callback/etc to put package_info in the database

            url = join_url_path(self.repo_url, package_info['relative_url_path'])

            file_name = package_info['relative_url_path'].rsplit('/', 1)[-1]
            destination = os.path.join(self.dst_dir, file_name)

            data = {'_id': ObjectId()}

            request = DownloadRequest(url, destination, data)
            download_request_list.append(request)

        self.downloader.download(download_request_list)


class PackagesDownloadEventListener(DownloadEventListener):
    # on start, save package info to db

    # on success
    # * validate package
    # * move package file into place

    # on failure
    # * delete package info from db
    # * error out?
    # * log error?

    def download_succeeded(self, report):
        # TODO logic/callback/etc to validate package and move it to destination
        pass

    def download_failed(self, report):
        # TODO logic/callback/etc to remove package_info from the database
        pass

# utility functions ------------------------------------------------------------

def join_url_path(url, relative_path):
    if url.endswith('/'):
        url = url[:-1]
    if relative_path.startswith('/'):
        relative_path = relative_path[1:]
    return '/'.join((url, relative_path))

