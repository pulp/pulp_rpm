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

from cStringIO import StringIO
from urlparse import urljoin
import math
import os
import shutil
import tempfile
import unittest

import mock

from pulp_rpm.common import ids, models


class TestISO(unittest.TestCase):
    """
    Test the ISO class.
    """
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test___init__(self):
        """
        Make sure __init__() sets all the proper attributes.
        """
        iso = models.ISO('name', 42, 'checksum')

        self.assertEqual(iso.name, 'name')
        self.assertEqual(iso.size, 42)
        self.assertEqual(iso.checksum, 'checksum')
        self.assertEqual(iso._unit, None)

    def test_from_unit(self):
        """
        Test correct behavior from the from_unit() method.
        """
        unit = mock.MagicMock()
        unit.unit_key = {'name': 'name', 'size': 42, 'checksum': 'checksum'}

        iso = models.ISO.from_unit(unit)

        self.assertEqual(iso.name, 'name')
        self.assertEqual(iso.size, 42)
        self.assertEqual(iso.checksum, 'checksum')
        self.assertEqual(iso._unit, unit)

    def test_init_unit(self):
        """
        Assert correct behavior from the init_unit() method.
        """
        unit = mock.MagicMock()
        conduit = mock.MagicMock()
        conduit.init_unit = mock.MagicMock(return_value=unit)
        iso = models.ISO('name', 42, 'checksum')

        iso.init_unit(conduit)

        self.assertEqual(iso._unit, unit)
        expected_relative_path = os.path.join('name', 'checksum', '42', 'name')
        conduit.init_unit.assert_called_once_with(
            ids.TYPE_ID_ISO, {'name': 'name', 'size': 42, 'checksum': 'checksum'}, {}, expected_relative_path)

    def test_save_unit(self):
        unit = mock.MagicMock()
        iso = models.ISO('name', 42, 'checksum', unit)
        conduit = mock.MagicMock()

        iso.save_unit(conduit)

        conduit.save_unit.assert_called_once_with(unit)

    def test_storage_path(self):
        """
        Make sure the storage_path() method returns the underlying Unit's storage_path attribute.
        """
        unit = mock.MagicMock()
        unit.storage_path = '/some/path'
        iso = models.ISO('name', 42, 'checksum', unit)

        storage_path = iso.storage_path

        self.assertEqual(storage_path, unit.storage_path)

    def test_validate(self):
        """
        Assert that validate() raises no Exception when passed correct data.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write("I heard there was this band called 1023MB, they haven't got any gigs yet.")
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 73, '36891c265290bf4610b488a8eb884d32a29fd17bb9886d899e75f4cf29d3f464',
                         unit)

        # This should validate, i.e., should not raise any Exception
        iso.validate()

    def test_validate_wrong_checksum(self):
        """
        Assert that validate() raises a ValueError when the checksum is not correct.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write('Two chemists walk into a bar, the first one says "I\'ll have some H2O." to '
                            'which the other adds "I\'ll have some H2O, too." The second chemist died.')
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 146, 'terrible_pun', unit)

        # This should raise a ValueError with an appropriate error message
        try:
            iso.validate()
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed checksum validation. The manifest specified the '
                        'checksum to be terrible_pun, but it was '
                        'dfec884065223f24c3ef333d4c7dcc0eb785a683cfada51ce071410b32a905e8.')

    def test_validate_wrong_size(self):
        """
        Assert that validate() raises a ValueError when given an incorrect size.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write("Hey girl, what's your sine? It must be math.pi/2 because you're the 1.")
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', math.pi,
                         '2b046422425d6f01a920278c55d8842a8989bacaea05b29d1d2082fae91c6041', unit)

        # This should raise a ValueError with an appropriate error message
        try:
            iso.validate()
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed validation. The manifest specified that the '
                        'file should be 3.14159265359 bytes, but the downloaded file is 70 bytes.')


class TestISOManifest(unittest.TestCase):
    """
    Test the ISOManifest class.
    """
    def test___init__(self):
        """
        Assert good behavior from the __init__() method.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,checksum2,2\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        manifest = models.ISOManifest(manifest_file, repo_url)

        # There should be three ISOs with all the right stuff
        self.assertEqual(len(manifest._isos), 3)
        for index, iso in enumerate(manifest._isos):
            self.assertEqual(iso.name, 'test%s.iso' % (index + 1))
            self.assertEqual(iso.size, index + 1)
            self.assertEqual(iso.checksum, 'checksum%s' % (index + 1))
            self.assertEqual(iso.url, urljoin(repo_url, iso.name))
            self.assertEqual(iso._unit, None)

    def test___init___with_malformed_manifest(self):
        """
        Assert good behavior from the __init__() method.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,doesnt_have_a_size\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        self.assertRaises(ValueError, models.ISOManifest, manifest_file, repo_url)

    def test___iter__(self):
        """
        Test the ISOManifest's __iter__() method.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,checksum2,2\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        manifest = models.ISOManifest(manifest_file, repo_url)

        num_isos = 0
        for iso in manifest:
            self.assertTrue(isinstance(iso, models.ISO))
            num_isos += 1
        self.assertEqual(num_isos, 3)

    def test___len__(self):
        """
        The ISOManifest should support the use of len() to return the number of ISOs it contains.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,checksum2,2\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        manifest = models.ISOManifest(manifest_file, repo_url)

        self.assertEqual(len(manifest), 3)
