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
from xml.etree.ElementTree import iterparse

from nectar.downloaders.revent import HTTPEventletRequestsDownloader
from nectar.request import DownloadRequest


def package_list_generator(xml_handle, package_tag, processor):
    """
    Parser for primary.xml file that is implemented as a generator.

    This generator reads enough of the primary.xml file into memory to parse a
    single package's information. It then yields a corresponding package
    information dictionary. Then repeats.

    :param xml_handle: open file handle pointing to the beginning of a primary.xml file
    :type  xml_handle: file-like object
    :return: generator of package information dictionaries
    :rtype: generator
    """
    parser = iterparse(xml_handle, events=('start', 'end'))
    xml_iterator = iter(parser)

    # get a hold of the root element so we can clear it
    # this prevents the entire parsed document from building up in memory
    root_element = xml_iterator.next()[1]

    for event, element in xml_iterator:
        # if we're not at a fully parsed package element, keep going
        if event != 'end' or element.tag != package_tag:
            continue

        root_element.clear() # clear all previously parsed ancestors of the root

        package_info = processor(element)
        yield package_info


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

    def __init__(self, repo_url, nectar_config, package_model_iterator, dst_dir, event_listener=None):
        self.repo_url = repo_url
        self.package_model_iterator = package_model_iterator
        self.dst_dir = dst_dir

        self.downloader = HTTPEventletRequestsDownloader(nectar_config, event_listener)

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
        for model in self.package_model_iterator:
            url = urljoin(self.repo_url, model.download_path)

            file_name = model.relative_path.rsplit('/', 1)[-1]
            destination = os.path.join(self.dst_dir, file_name)

            request = DownloadRequest(url, destination, model)
            yield request
