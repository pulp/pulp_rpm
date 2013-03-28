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

import gzip
import os
import StringIO
import unittest

from pulp_rpm.plugins.importers.download import primary, packages


TEST_REPO_PRIMARY_XML_PATH = '../data/test_repo/repodata/primary.xml.gz'


class PrimaryXMLParserTests(unittest.TestCase):

    def test_generator_instantiation(self):
        handle = StringIO.StringIO()
        try:
            packages.package_list_generator(
                handle, primary.PACKAGE_TAG, primary.process_package_element
            )
        except Exception, e:
            self.fail(str(e))
        finally:
            handle.close()

    def test_compressed_primary(self):
        current_path = os.path.dirname(__file__)
        primary_xml_path = os.path.join(current_path, TEST_REPO_PRIMARY_XML_PATH)
        handle =  gzip.open(primary_xml_path, 'r')
        generator = packages.package_list_generator(
            handle, primary.PACKAGE_TAG, primary.process_package_element
        )

        for file_info in generator:
            # assert the file_info dictionaries were built correctly by looking
            # for keys from each section
            self.assertTrue('type' in file_info)
            self.assertFalse(file_info['type'] is None)
            self.assertTrue('vendor' in file_info)

        handle.close()
