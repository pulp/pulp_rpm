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

import math
import os
import shutil
import tempfile
import unittest

from pulp_rpm.common import models

class TestValidate(unittest.TestCase):
    """
    Test the pulp_rpm.common.models.ISO.validate() method.
    """
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
            shutil.rmtree(self.temp_dir)

    def test_with_regular_file(self):
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write("I heard there was this band called 1023MB, they haven't got any gigs yet.")
        iso = models.ISO('test.txt', 73, '36891c265290bf4610b488a8eb884d32a29fd17bb9886d899e75f4cf29d3f464')
        iso.storage_path = destination

        # This should validate, i.e., should not raise any Exception
        iso.validate()

    def test_wrong_checksum(self):
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write('Two chemists walk into a bar, the first one says "I\'ll have some H2O." to '
                            'which the other adds "I\'ll have some H2O, too." The second chemist died.')
        iso = models.ISO('test.txt', 146, 'terrible_pun')
        iso.storage_path = destination

        # This should raise a ValueError with an appropriate error message
        try:
            iso.validate()
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed checksum validation. The manifest specified the '
                        'checksum to be terrible_pun, but it was '
                        'dfec884065223f24c3ef333d4c7dcc0eb785a683cfada51ce071410b32a905e8.')

    def test_wrong_size(self):
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write("Hey girl, what's your sine? It must be math.pi/2 because you're the 1.")
        iso = models.ISO('test.txt', math.pi,
                         '2b046422425d6f01a920278c55d8842a8989bacaea05b29d1d2082fae91c6041')
        iso.storage_path = destination

        # This should raise a ValueError with an appropriate error message
        try:
            iso.validate()
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed validation. The manifest specified that the '
                        'file should be 3.14159265359 bytes, but the downloaded file is 70 bytes.')
