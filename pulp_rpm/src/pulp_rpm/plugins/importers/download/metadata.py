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

import hashlib
import os
from copy import deepcopy
from urlparse import urljoin
from xml.etree.cElementTree import iterparse


from pulp.common.download.downloaders.curl import HTTPSCurlDownloader
from pulp.common.download.config import DownloaderConfig
from pulp.common.download.request import DownloadRequest

# repomd.xml element tags ------------------------------------------------------

REPOMD_FILE_NAME = 'repomd.xml'
REPOMD_URL_RELATIVE_PATH = 'repodata/%s' % REPOMD_FILE_NAME

SPEC_URL = 'http://linux.duke.edu/metadata/repo'

REVISION_TAG = '{%s}revision' % SPEC_URL

DATA_TAG = '{%s}data' % SPEC_URL

LOCATION_TAG = '{%s}location' % SPEC_URL
CHECKSUM_TAG = '{%s}checksum' % SPEC_URL
SIZE_TAG = '{%s}size' % SPEC_URL
TIMESTAMP_TAG = '{%s}timestamp' % SPEC_URL
OPEN_CHECKSUM_TAG = '{%s}open-checksum' % SPEC_URL
OPEN_SIZE_TAG = '{%s}open-size' % SPEC_URL

# metadata file information skeleton -------------------------------------------

FILE_INFO_SKEL = {'name': None,
                  'relative_path': None,
                  'checksum': {'algorithm': None, 'hex_digest': None},
                  'size': None,
                  'timestamp': None,
                  'open_checksum': {'algorithm': None, 'hex_digest': None},
                  'open_size': None}

# metadata files downloader, parser, and validator -----------------------------

class MetadataFiles(object):
    """
    Stateful downloader, parser, and validator of the metadata files of a Yum
    repository.

    Given a Yum repository URL, this class presents a clean work flow for
    fetching and validating the metadata files of that repo. The workflow is as
    follows:

    1. instantiate MetadataFiles instance with repository URL
    2. call `download_repomd` method
    3. call `parse_repomd` method
    4. call `download_metadata_files` method
    5. optionally call `validate_metadata_files` method

    If all goes well, the instance will have have populated its `metadata` dict
    with `key` -> file path information

    Keys of interest:

     * `primary`: path the primary.xml file containing the metadata of all packages in the repository
     * `filelists`: path the filelists.xml file containing the files provided by all of the packages in the repository
     * `other`
     * `group`
     * `group_gz`
     * `updateinfo`

    :ivar repo_url: Yum repository URL
    :ivar dst_dir: Directory to store downloaded metadata files in
    :ivar event_listener: pulp.common.download.listener.DownloadEventListener instance
    :ivar downloader: pulp.common.download.backends.base.DownloaderBackend instance
    :ivar revision: revision number of the metadata, set during the `parse_repomd` call
    :ivar metadata: dictionary of the main metadata type keys to the corresponding file paths
    """

    def __init__(self, repo_url, dst_dir, event_listener=None):
        super(MetadataFiles, self).__init__()
        self.repo_url = repo_url
        self.dst_dir = dst_dir

        downloader_config = DownloaderConfig()
        self.downloader = HTTPSCurlDownloader(downloader_config, event_listener)

        self.revision = None
        self.metadata = {}

    def download_repomd(self):
        """
        Download the main repomd.xml file.
        """
        repomd_dst_path = os.path.join(self.dst_dir, REPOMD_FILE_NAME)
        repomd_url = urljoin(self.repo_url, REPOMD_URL_RELATIVE_PATH)
        repomd_request = DownloadRequest(repomd_url, repomd_dst_path)
        self.downloader.download([repomd_request])

    # TODO (jconnonr 2013-03-07) add a method to validate/verify the repomd.xml file

    def parse_repomd(self):
        """
        Parse the downloaded repomd.xml file and populate the metadata dictionary.
        """
        repomd_file_path = os.path.join(self.dst_dir, REPOMD_FILE_NAME)

        if not os.access(repomd_file_path, os.F_OK | os.R_OK):
            raise RuntimeError('%s has not been downloaded' % REPOMD_FILE_NAME)

        parser = iterparse(repomd_file_path, events=('start', 'end'))
        xml_iterator = iter(parser)

        # get a hold of the root element so that we can clear it
        # this prevents the entire parsed document from building up in memory
        root_element = xml_iterator.next()[1]

        for event, element in xml_iterator:
            if event != 'end':
                continue

            root_element.clear()

            if element.tag == REVISION_TAG:
                self.revision = element.text

            if element.tag == DATA_TAG:
                file_info = process_repomd_data_element(element)
                self.metadata[file_info['name']] = file_info

    def download_metadata_files(self):
        """
        Download the remaining metadata files.
        """
        if not self.metadata:
            raise RuntimeError('%s has not been parsed' % REPOMD_FILE_NAME)

        download_request_list = []

        for md in self.metadata.values():
            url = urljoin(self.repo_url, md['relative_path'])
            dst = os.path.join(self.dst_dir, md['relative_path'].rsplit('/', 1)[-1])

            md['local_path'] = dst

            request = DownloadRequest(url, dst)
            download_request_list.append(request)

        self.downloader.download(download_request_list)

    def verify_metadata_files(self):
        """
        Optionally verify the metadata files using both reported size and checksum.
        """
        for md in self.metadata.values():
            if 'local_path' not in md:
                raise RuntimeError('%s has not been downloaded' % md['relative_path'].rsplit('/', 1)[-1])

            if md['size'] is None:
                raise RuntimeError('%s cannot be verified, no file size' % md['local_path'])

            local_file_size = os.path.getsize(md['local_path'])
            # prevents the rounding errors better than: md['size'] * 1024
            if local_file_size / 1024 != md['size']:
                raise RuntimeError('%s failed verification, file size mismatch' % md['local_path'])

            if md['checksum']['algorithm'] is None:
                raise RuntimeError('%s cannot be verified, no checksum' % md['local_path'])

            hash_constructor = getattr(hashlib, md['checksum']['algorithm'], None)
            if hash_constructor is None:
                raise RuntimeError('%s failed verification, unsupported hash algorithm: %s' % (md['local_path'], md['checksum']['algorithm']))

            hash_obj = hash_constructor()
            with open(md['local_path'], 'rb') as file_handle:
                hash_obj.update(file_handle.read())
            if hash_obj.hexdigest() != md['checksum']['hex_digest']:
                raise RuntimeError('%s failed verification, checksum mismatch' % md['local_path'])

# utilities --------------------------------------------------------------------

def process_repomd_data_element(data_element):
    """
    Process the data elements of the repomd.xml file.

    This returns a file information dictionary with the following keys:

     * `name`: name of the element
     * `relative_path`: the path of the metadata file, relative to the repository URL
     * `checksum`: dictionary of `algorithm` and `hex_digest` keys and values
     * `size`: size of the metadata file, in bytes
     * `timestamp`: unix timestamp of the file's creation, as a float
     * `open_checksum`: optional checksum dictionary of uncompressed metadata file
     * `open_size`: optional size of the uncompressed metadata file, in bytes

    :param data_element: XML data element parsed from the repomd.xml file
    :return: file_info dictionary
    :rtype: dict
    """

    file_info = deepcopy(FILE_INFO_SKEL)

    file_info['name'] = data_element.attrib['type']

    location_element = data_element.find(LOCATION_TAG)
    if location_element is not None:
        file_info['relative_path'] = location_element.attrib['href']

    checksum_element = data_element.find(CHECKSUM_TAG)
    if checksum_element is not None:
        file_info['checksum']['algorithm'] = checksum_element.attrib['type']
        file_info['checksum']['hex_digest'] = checksum_element.text

    size_element = data_element.find(SIZE_TAG)
    if size_element is not None:
        file_info['size'] = int(size_element.text)

    timestamp_element = data_element.find(TIMESTAMP_TAG)
    if timestamp_element is not None:
        file_info['timestamp'] = float(timestamp_element.text)

    open_checksum_element = data_element.find(OPEN_CHECKSUM_TAG)
    if open_checksum_element is not None:
        file_info['open_checksum']['algorithm'] = open_checksum_element.attrib['type']
        file_info['open_checksum']['hex_digest'] = open_checksum_element.text

    open_size_element = data_element.find(OPEN_SIZE_TAG)
    if open_size_element is not None:
        file_info['open_size'] = int(open_size_element.text)

    for child in data_element.getchildren():
        child.clear()
    data_element.clear()

    return file_info

