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
import StringIO
import unittest

from pulp_rpm.plugins.importers.download import primary


TEST_REPO_PRIMARY_XML_PATH = '../data/test_repo/repodata/primary.xml.gz'


class PrimaryXMLParserTests(unittest.TestCase):

    def test_generator_instantiation(self):
        handle = StringIO.StringIO()
        try:
            primary.primary_package_list_generator(handle)
        except Exception, e:
            self.fail(str(e))
        finally:
            handle.close()

    def test_compressed_primary(self):
        with gzip.open(TEST_REPO_PRIMARY_XML_PATH, 'r') as handle:
            generator = primary.primary_package_list_generator(handle)

            for file_info in generator:
                # assert the file_info dictionaries were built correctly by looking
                # for keys from each section
                self.assertTrue('type' in file_info)
                self.assertFalse(file_info['type'] is None)
                self.assertTrue('vendor' in file_info)

