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

import os
from xml.etree import ElementTree

from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    PreGeneratedMetadataContext, REPO_DATA_DIR_NAME)
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

OTHER_XML_FILE_NAME = 'other.xml.gz'
OTHER_NAMESPACE = 'http://linux.duke.edu/metadata/other'


class OtherXMLFileContext(PreGeneratedMetadataContext):
    """
    Context manager for generating the other.xml.gz file.
    """

    def __init__(self, working_dir, num_units):
        """
        :param working_dir: working directory to create the other.xml.gz in
        :type  working_dir: str
        :param num_units: total number of units whose metadata will be written
                          into the other.xml.gz metadata file
        :type  num_units: int
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, OTHER_XML_FILE_NAME)
        super(OtherXMLFileContext, self).__init__(metadata_file_path)

        self.num_packages = num_units

    def _write_root_tag_open(self):

        attributes = {'xmlns': OTHER_NAMESPACE,
                      'packages': str(self.num_packages)}

        metadata_element = ElementTree.Element('otherdata', attributes)
        bogus_element = ElementTree.SubElement(metadata_element, '')

        metadata_tags_string = ElementTree.tostring(metadata_element, 'utf-8')
        # use a bogus sub-element to programmaticly split the opening and closing tags
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = metadata_tags_string.split(bogus_tag_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_unit_metadata(self, unit):

        self._add_unit_pre_generated_metadata('other', unit)

