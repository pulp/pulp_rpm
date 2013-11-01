# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import unittest
import os

import mock

from pulp_rpm.common import file_utils

DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/data'


class TestFileUtils(unittest.TestCase):

    def setUp(self):
        self.test_file = os.path.join(DATA_DIR, "cert.key")

    def test_calculate_checksum(self):
        test_file = open(self.test_file)
        try:
            file_checksum = file_utils.calculate_checksum(test_file)
        finally:
            test_file.close()

        self.assertEquals(file_checksum, '4da653eb38433cd3bfb0910453f836267a91336'
                                         '635d23f047aaecca1b2b960cd')

    def test_calculate_size(self):
        test_file = open(self.test_file)
        try:
            file_size = file_utils.calculate_size(test_file)
        finally:
            test_file.close()

        self.assertEquals(file_size, 1675)
