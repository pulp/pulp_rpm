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
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import bz2
import gzip
import hashlib
import os
import time
from xml.etree import ElementTree

from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    MetadataFileContext, REPO_DATA_DIR_NAME)
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

REPOMD_FILE_NAME = 'repomd.xml'

DEFAULT_CHECKSUM_TYPE = 'sha256'

REPO_XML_NAME_SPACE = 'http://linux.duke.edu/metadata/repo'
RPM_XML_NAME_SPACE = 'http://linux.duke.edu/metadata/rpm'


class RepomdXMLFileContext(MetadataFileContext):

    def __init__(self, working_dir, checksum_type=DEFAULT_CHECKSUM_TYPE):
        assert checksum_type in hashlib.algorithms

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, REPOMD_FILE_NAME)
        super(RepomdXMLFileContext, self).__init__(metadata_file_path)

        self.checksum_type = checksum_type
        self.checksum_constructor = getattr(hashlib, checksum_type)

    def _write_root_tag_open(self):

        repomd_attributes = {'xmlns': REPO_XML_NAME_SPACE,
                             'xmlns:rpm': RPM_XML_NAME_SPACE}

        repomd_element = ElementTree.Element('repomd', repomd_attributes)

        revision_element = ElementTree.SubElement(repomd_element, 'revision')
        revision_element.text = str(int(time.time()))

        bogus_element = ElementTree.SubElement(repomd_element, '')

        repomd_element_string = ElementTree.tostring(repomd_element, 'utf-8')

        bogus_element_string = ElementTree.tostring(bogus_element, 'utf-8')

        opening_tag, closing_tag = repomd_element_string.split(bogus_element_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        # Setup the corresponding _write_root_tag_close as a closure

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_metadata_file_metadata(self, data_type, file_path):

        data_attributes = {'type': data_type}
        data_element = ElementTree.Element('data', data_attributes)

        location_element = ElementTree.SubElement(data_element, 'location')
        location_element.text = os.path.join(REPO_DATA_DIR_NAME, os.path.basename(file_path))

        timestamp_element = ElementTree.SubElement(data_element, 'timestamp')
        timestamp_element.text = str(os.path.getmtime(file_path))

        size_element = ElementTree.SubElement(data_element, 'size')
        size_element.text = str(os.path.getsize(file_path))

        checksum_attributes = {'type': self.checksum_type}
        checksum_element = ElementTree.SubElement(data_element, 'checksum', checksum_attributes)

        with open(file_path, 'rb') as file_handle:
            content = file_handle.read()
            checksum_element.text = self.checksum_constructor(content).hexdigest()

        if file_path.endswith('.gz'):

            open_size_element = ElementTree.SubElement(data_element, 'open-size')

            open_checksum_attributes = {'type': self.checksum_type}
            open_checksum_element = ElementTree.SubElement(data_element, 'open-checksum', open_checksum_attributes)

            with gzip.open(file_path, 'r') as file_handle:
                content = file_handle.read()
                open_size_element.text = str(len(content))
                open_checksum_element.text = self.checksum_constructor(content).hexdigest()

        # Write the metadata out as a utf-8 string

        data_element_string = ElementTree.tostring(data_element, 'utf-8')

        _LOG.debug('Writing repomd metadata:\n' + data_element_string)

        self.metadata_file_handle.write(data_element_string + '\n')


