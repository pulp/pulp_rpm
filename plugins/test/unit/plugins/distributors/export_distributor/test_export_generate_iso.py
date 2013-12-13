# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os
import stat
import sys
import unittest
import datetime

import mock

# pulp_rpm/pulp_rpm/plugins/distributors/iso_distributor isn't in the python path
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/distributors/")
from pulp_rpm.plugins.distributors.export_distributor import generate_iso


class TestCreateIso(unittest.TestCase):
    """
    Test the create_iso method in generate_iso
    """
    def setUp(self):
        self.get_dir_file_list = generate_iso._get_dir_file_list_and_size
        self.make_iso = generate_iso._make_iso
        self.compute_image_files = generate_iso._compute_image_files

        generate_iso._get_dir_file_list_and_size = mock.Mock(return_value=(['files'], 55))
        generate_iso._make_iso = mock.Mock()
        generate_iso._compute_image_files = mock.Mock(return_value=['list'])

    def tearDown(self):
        generate_iso._get_dir_file_list_and_size = self.get_dir_file_list
        generate_iso._make_iso = self.make_iso
        generate_iso._compute_image_files = self.compute_image_files

    def test_create_iso(self):
        """
        Test that the create_iso method calls its helpers correctly
        """
        # Assert all the helper methods were called correctly
        generate_iso.create_iso('/target/dir', '/output/dir', 'prefix')
        generate_iso._get_dir_file_list_and_size.assert_called_once_with('/target/dir')
        generate_iso._compute_image_files.assert_called_once_with(['files'], generate_iso.DVD_ISO_SIZE *
                                                                  1024 * 1024)
        self.assertEqual('list', generate_iso._make_iso.call_args[0][0])
        self.assertEqual('/target/dir', generate_iso._make_iso.call_args[0][1])
        self.assertEqual('/output/dir', generate_iso._make_iso.call_args[0][2])


class TestMakeIso(unittest.TestCase):
    """
    Test the _make_iso helper method in generate_iso
    """
    @mock.patch('os.path.isdir', autospec=True, return_value=True)
    @mock.patch('os.close', autospec=True)
    @mock.patch('os.unlink', autospec=True)
    @mock.patch('commands.getstatusoutput', autospec=True, return_value=(0, 'out'))
    @mock.patch('tempfile.mkstemp', autospec=True, return_value=('file_descriptor', 'spec_file'))
    def test_make_iso(self, mock_mkstemp, mock_cmd, mock_unlink, mock_close, mock_isdir):
        # Setup
        timestamp = datetime.datetime.now()
        output_dir = '/output/dir'
        filename = 'prefix-%s-01.iso' % timestamp.strftime("%Y-%m-%dT%H.%M")
        file_path = os.path.join(output_dir, filename)
        expected_command = "mkisofs -r -D -graft-points -path-list spec_file -o %s" % file_path

        # Test
        generate_iso._make_iso([], '/target/dir', output_dir, filename)
        mock_cmd.assert_called_once_with(expected_command)
        mock_unlink.assert_called_once_with('spec_file')
        self.assertEqual(1, mock_mkstemp.call_count)
        self.assertEqual(1, mock_close.call_count)
        self.assertEqual(1, mock_isdir.call_count)

    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('os.path.isdir', autospec=True, return_value=False)
    @mock.patch('os.close', autospec=True)
    @mock.patch('os.unlink', autospec=True)
    @mock.patch('commands.getstatusoutput', autospec=True, return_value=(0, 'out'))
    @mock.patch('tempfile.mkstemp', autospec=True, return_value=('file_descriptor', 'spec_file'))
    def test_missing_output_dir(self, mock_mkstemp, mock_cmd, mock_unlink, mock_close, mock_isdir,
                                mock_makedirs):
        # Setup
        timestamp = datetime.datetime.now()
        filename = '/output/dir/prefix-%s-01.iso' % timestamp.strftime("%Y-%m-%dT%H.%M")
        expected_command = "mkisofs -r -D -graft-points -path-list spec_file -o %s" % filename

        # Test that the directory is made and the iso is created like it normally would
        generate_iso._make_iso([], '/target/dir', '/output/dir', filename)
        mock_makedirs.assert_called_once_with('/output/dir')
        mock_cmd.assert_called_once_with(expected_command)
        mock_unlink.assert_called_once_with('spec_file')
        self.assertEqual(1, mock_mkstemp.call_count)
        self.assertEqual(1, mock_close.call_count)
        self.assertEqual(1, mock_isdir.call_count)


class TestParseImageSize(unittest.TestCase):
    """
    Test the _parse_image_size helper method in generate_iso
    """
    def test_non_int(self):
        # Assert a ValueError is raised when something that isn't an int is given
        self.assertRaises(ValueError, generate_iso._parse_image_size, 'I\'ve made a huge mistake')

    def test_zero_size(self):
        # Assert a ValueError is raised when a value less than 1 is given
        self.assertRaises(ValueError, generate_iso._parse_image_size, 0)

    def test_none(self):
        # Assert that if None is received, the size is set to a dvd-sized ISO
        result = generate_iso._parse_image_size(None)
        self.assertEqual(generate_iso.DVD_ISO_SIZE * 1024 * 1024, result)

    def test_parse_image_size(self):
        # Confirm things work as expected with a sane value
        result = generate_iso._parse_image_size(100)
        self.assertEqual(100 * 1024 * 1024, result)


class TestComputeImageFiles(unittest.TestCase):
    """
    Test the _compute_image_files helper method in generate_iso
    """
    def test_file_larger_than_image(self):
        # Setup
        max_image_size = 5
        file_list = [('path1', 1), ('path2', 2), ('path3', 1000), ('path4', 1)]

        # Assert than a ValueError is raised when the maximum image size is smaller than a file size
        self.assertRaises(ValueError, generate_iso._compute_image_files, file_list, max_image_size)

    def test_multi_iso_list(self):
        # Setup
        image_size = 5
        file_list = [('path1', 1), ('path2', 2), ('path3', 2), ('path4', 4), ('path5', 3)]

        # Test
        images = generate_iso._compute_image_files(file_list, image_size)
        self.assertEqual(3, len(images))
        self.assertEqual(images[0], [file_list[0][0], file_list[1][0], file_list[2][0]])
        self.assertEqual(images[1], [file_list[3][0]])
        self.assertEqual(images[2], [file_list[4][0]])


class TestGetGraft(unittest.TestCase):
    """
    Test the _get_grafts helper method in generate_iso
    """
    def test_get_grafts(self):
        # Setup
        files = ['/target/dir/path1', '/target/dir/relative/path2']
        target_dir = '/target/dir'
        expected_grafts = ['/./=/target/dir/path1', '/relative/=/target/dir/relative/path2']

        # Test
        grafts = generate_iso._get_grafts(files, target_dir)
        self.assertEqual(expected_grafts, grafts)


class TestGetPathSpecFile(unittest.TestCase):
    """
    test the _get_pathspec_file helper method in generate_iso
    """
    @mock.patch('os.close', autospec=True)
    @mock.patch('os.write', autospec=True)
    @mock.patch('tempfile.mkstemp', autospec=True, return_value=('descriptor', 'filename'))
    def test_get_pathspec(self, mock_mkstemp, mock_write, mock_close):
        # Setup
        file_list = ['/target/dir/path']
        target_dir = '/target/dir'
        expected_graft = '/./=/target/dir/path\n'

        # Test
        result = generate_iso._get_pathspec_file(file_list, target_dir)
        self.assertEqual('filename', result)
        mock_mkstemp.assert_called_once_with(dir=target_dir, prefix='pulpiso-')
        mock_write.assert_called_once_with('descriptor', expected_graft)
        mock_close.assert_called_once_with('descriptor')


class TestGetDirFileListAndSize(unittest.TestCase):
    """
    Test the _get_dir_file_list_and_size helper method in generate_iso
    """
    @mock.patch('os.stat', autospec=True, return_value={stat.ST_SIZE: 10})
    @mock.patch('os.walk', autospec=True, return_value=[('/root', ['dir'], ['file1'])])
    def test_get_dir_file_list(self, mock_walk, mock_stat):
        # Setup
        expected_file_list = [('/root/file1', 10)]

        # Test that our silly walk mock is called, and that the correct file list and size is returned
        file_list, total_size = generate_iso._get_dir_file_list_and_size('/target/dir')
        mock_walk.assert_called_once_with('/target/dir')
        self.assertEqual(expected_file_list, file_list)
        self.assertEqual(10, total_size)
        mock_stat.assert_called_once_with('/root/file1')