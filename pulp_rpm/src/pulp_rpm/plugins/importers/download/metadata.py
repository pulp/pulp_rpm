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

from cStringIO import StringIO
from datetime import datetime
from pprint import pprint
from xml.etree.cElementTree import iterparse


from pulp.common.download import factory as download_factory
from pulp.common.download.config import DownloaderConfig
from pulp.common.download.listener import DownloadEventListener
from pulp.common.download.request import DownloadRequest


REPOMD_RELATIVE_PATH = 'repodata/repomd.xml'

SPEC_URL = 'http://linux.duke.edu/metadata/repo'

REVISION_TAG = '{%s}revision' % SPEC_URL

DATA_TAG = '{%s}data' % SPEC_URL

LOCATION_TAG = '{%s}location' % SPEC_URL
CHECKSUM_TAG = '{%s}checksum' % SPEC_URL
SIZE_TAG = '{%s}size' % SPEC_URL
OPEN_CHECKSUM_TAG = '{%s}open-checksum' % SPEC_URL
OPEN_SIZE_TAG = '{%s}open-size' % SPEC_URL


class MetadataFiles(DownloadEventListener):

    def __init__(self, repo_url):
        super(MetadataFiles, self).__init__()
        self.repo_url = repo_url

        downloader_config = DownloaderConfig('https')
        self.downloader = download_factory.get_downloader(downloader_config, self)

        self.raw_metadata_xml_io = StringIO()

        self.revision = None
        self.metadata = {}

    def download_succeeded(self, report):
        self.raw_metadata_xml_io.seek(0)

    def download_failed(self, report):
        raise RuntimeError('%s download failed' % REPOMD_RELATIVE_PATH)

    def download_repomd(self):
        repomd_url = join_url_path(self.repo_url, REPOMD_RELATIVE_PATH)
        repomd_request = DownloadRequest(repomd_url, self.raw_metadata_xml_io)
        self.downloader.download([repomd_request])

    def parse_repomd(self):
        parser = iterparse(self.raw_metadata_xml_io, events=('start', 'end'))
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

        root_element.clear()

# utilities --------------------------------------------------------------------

def process_repomd_data_element(data_element):

    file_info = {'name': data_element.attrib['type']}

    location_element = data_element.find(LOCATION_TAG)
    if location_element is not None:
        file_info['relative_path'] = location_element.attrib['href']

    checksum_element = data_element.find(CHECKSUM_TAG)
    if checksum_element is not None:
        file_info['checksum'] = {'algorithm': checksum_element.attrib['type'],
                                 'value': checksum_element.text}

    size_element = data_element.find(SIZE_TAG)
    if size_element is not None:
        file_info['size'] = int(size_element.text)

    open_checksum_element = data_element.find(OPEN_CHECKSUM_TAG)
    if open_checksum_element is not None:
        file_info['open_checksum'] = {'algorithm': open_checksum_element.attrib['type'],
                                      'value': open_checksum_element.text}

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

# main -------------------------------------------------------------------------

def download_metadata(repo_url):
    start = datetime.now()
    metadata_files = MetadataFiles(repo_url)
    metadata_files.download_repomd()
    metadata_files.parse_repomd()
    finish = datetime.now()
    pprint(metadata_files.metadata)
    print 'time elapsed: %s' % str(finish - start)


if __name__ == '__main__':
    repo_url = 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/'
    download_metadata(repo_url)
