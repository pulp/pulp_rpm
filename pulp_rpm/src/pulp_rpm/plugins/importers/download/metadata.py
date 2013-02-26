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
from datetime import datetime
from pprint import pprint
from tempfile import mkdtemp
from xml.etree.cElementTree import iterparse


from pulp.common.download import factory as download_factory
from pulp.common.download.config import DownloaderConfig
from pulp.common.download.listener import DownloadEventListener
from pulp.common.download.request import DownloadRequest


REPOMD_FILE_NAME = 'repomd.xml'
REPOMD_URL_RELATIVE_PATH = 'repodata/%s' % REPOMD_FILE_NAME

SPEC_URL = 'http://linux.duke.edu/metadata/repo'

REVISION_TAG = '{%s}revision' % SPEC_URL

DATA_TAG = '{%s}data' % SPEC_URL

LOCATION_TAG = '{%s}location' % SPEC_URL
CHECKSUM_TAG = '{%s}checksum' % SPEC_URL
SIZE_TAG = '{%s}size' % SPEC_URL
OPEN_CHECKSUM_TAG = '{%s}open-checksum' % SPEC_URL
OPEN_SIZE_TAG = '{%s}open-size' % SPEC_URL


class MetadataFiles(object):

    def __init__(self, repo_url, dst_dir=None):
        super(MetadataFiles, self).__init__()
        self.repo_url = repo_url
        self.dst_dir = dst_dir or mkdtemp()

        downloader_config = DownloaderConfig('https')
        self.downloader = download_factory.get_downloader(downloader_config, MetadataDownloadEventListener())

        self.revision = None
        self.metadata = {}

    def download_repomd(self):
        repomd_dst_path = os.path.join(self.dst_dir, REPOMD_FILE_NAME)
        repomd_url = join_url_path(self.repo_url, REPOMD_URL_RELATIVE_PATH)
        repomd_request = DownloadRequest(repomd_url, repomd_dst_path)
        self.downloader.download([repomd_request])

    def parse_repomd(self):
        repomd_file_path = os.path.join(self.dst_dir, REPOMD_FILE_NAME)

        if not os.path.exists(repomd_file_path):
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
                # XXX cast this to an int?
                self.revision = element.text

            if element.tag == DATA_TAG:
                file_info = process_repomd_data_element(element)
                self.metadata[file_info['name']] = file_info

    def download_metadata_files(self):
        if not self.metadata:
            raise RuntimeError('%s has not been parsed' % REPOMD_FILE_NAME)

        download_request_list = []

        for md in self.metadata.values():
            url = join_url_path(self.repo_url, md['relative_path'])
            dst = os.path.join(self.dst_dir, md['relative_path'].rsplit('/', 1)[-1])

            md['local_path'] = dst

            request = DownloadRequest(url, dst)
            download_request_list.append(request)

        self.downloader.download(download_request_list)

    def verify_metadata_files(self):
        for md in self.metadata.values():
            if 'local_path' not in md:
                raise RuntimeError('%s has not been downloaded' % md['relative_path'].rsplit('/', 1)[-1])

            #if 'size' not in md:
            #    continue
            #    raise RuntimeError('%s cannot be verified, no file size' % md['local_path'])

            #local_file_size = os.path.getsize(md['local_path'])
            #if local_file_size != md['size'] * 1024:
            #    raise RuntimeError('%s failed verification, file size mismatch' % md['local_path'])

            if 'checksum' not in md:
                raise RuntimeError('%s cannot be verified, no checksum' % md['local_path'])

            hash_obj = getattr(hashlib, md['checksum']['algorithm'], hashlib.sha256)()
            file_handle = open(md['local_path'], 'rb')
            hash_obj.update(file_handle.read())
            file_handle.close()
            if hash_obj.hexdigest() != md['checksum']['hex_digest']:
                raise RuntimeError('%s failed verification, checksum mismatch' % md['local_path'])


class MetadataDownloadEventListener(DownloadEventListener):

    def download_failed(self, report):
        raise RuntimeError('%s download failed' % report.url)

# utilities --------------------------------------------------------------------

def process_repomd_data_element(data_element):

    file_info = {'name': data_element.attrib['type']}

    location_element = data_element.find(LOCATION_TAG)
    if location_element is not None:
        file_info['relative_path'] = location_element.attrib['href']

    checksum_element = data_element.find(CHECKSUM_TAG)
    if checksum_element is not None:
        file_info['checksum'] = {'algorithm': checksum_element.attrib['type'],
                                 'hex_digest': checksum_element.text}

    size_element = data_element.find(SIZE_TAG)
    if size_element is not None:
        file_info['size'] = int(size_element.text)

    open_checksum_element = data_element.find(OPEN_CHECKSUM_TAG)
    if open_checksum_element is not None:
        file_info['open_checksum'] = {'algorithm': open_checksum_element.attrib['type'],
                                      'hex_digest': open_checksum_element.text}

    open_size_element = data_element.find(OPEN_SIZE_TAG)
    if open_size_element is not None:
        file_info['open_size'] = int(open_size_element.text)

    for child in data_element.getchildren():
        child.clear()
    data_element.clear()

    return file_info


def join_url_path(url, relative_path):
    if url.endswith('/'):
        url = url[:-1]
    if relative_path.startswith('/'):
        relative_path = relative_path[1:]
    return '/'.join((url, relative_path))

