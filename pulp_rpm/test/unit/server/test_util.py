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

import os
import shutil
import sys
import tempfile
import unittest

import mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../src/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../plugins/importers/")

import rpm_support_base
from pulp_rpm.yum_plugin import util


class TestUtil(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(TestUtil, self).setUp()
        self.init()

    def tearDown(self):
        super(TestUtil, self).tearDown()
        self.clean()

    def init(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), "data"))

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def test_is_rpm_newer(self):
        rpm_a = {"name": "rpm_test_name", "epoch":"0", "release":"el6.1", "version":"2", "arch":"noarch"}
        newer_a = {"name": "rpm_test_name", "epoch":"0", "release":"el6.1", "version":"3", "arch":"noarch"}
        newer_a_diff_arch = {"name": "rpm_test_name", "epoch":"0", "release":"el6.1", "version":"2", "arch":"i386"}
        rpm_b = {"name": "rpm_test_name_B", "epoch":"0", "release":"el6.1", "version":"5", "arch":"noarch"}

        self.assertTrue(util.is_rpm_newer(newer_a, rpm_a))
        self.assertFalse(util.is_rpm_newer(newer_a_diff_arch, rpm_a))
        self.assertFalse(util.is_rpm_newer(rpm_a, newer_a))
        self.assertFalse(util.is_rpm_newer(newer_a, rpm_b))


class TestStringToUnicode(unittest.TestCase):
    def test_ascii(self):
        result = util.string_to_unicode('abc')
        self.assertTrue(isinstance(result, unicode))
        self.assertEqual(result, u'abc')

    def test_empty(self):
        result = util.string_to_unicode('')
        self.assertTrue(isinstance(result, unicode))
        self.assertEqual(result, u'')

    def test_latin1(self):
        data = '/usr/share/doc/man-pages-da-0.1.1/l\xe6smig'
        result = util.string_to_unicode(data)
        self.assertTrue(isinstance(result, unicode))
        self.assertEqual(result, data.decode('iso-8859-1'))

    def test_utf8(self):
        result = util.string_to_unicode(u'€'.encode('utf8'))
        self.assertTrue(isinstance(result, unicode))
        self.assertEqual(result, u'€')


class TestRemovePublishDir(unittest.TestCase):
    """
    This class tests the pulp_rpm.yum_plugin.util.remove_publish_dir function
    """

    @mock.patch('os.unlink', autospec=True)
    @mock.patch('os.path.dirname', autospec=True)
    def test_failed_unlink(self, mock_dirname, mock_unlink):
        """
        This test checks that remove_publish_dir handles receiving a link that is
        not a symlink gracefully
        """
        # Setup
        test_publish_dir = '/fake/publish/dir'
        test_link_path = '/fake/publish/dir/some/relative/url'
        mock_unlink.side_effect = OSError('I\'ve made a huge mistake')

        # Assert that we never make it to checking the parent directory of the link path
        util.remove_repo_publish_dir(test_publish_dir, test_link_path)
        self.assertEqual(test_link_path, mock_unlink.call_args[0][0])
        self.assertEqual(0, mock_dirname.call_count)

    @mock.patch('os.rmdir', autospec=True)
    @mock.patch('os.unlink', autospec=True)
    def test_remove_at_root(self, mock_unlink, mock_rmdir):
        """
        This tests removing a symlink at the root of the publishing directory.
        """
        # Setup
        test_publish_dir = '/fake/publish/dir'
        test_link_path = '/fake/publish/dir/repo'

        # Test that the link was removed and mock_rmdir never got called
        util.remove_repo_publish_dir(test_publish_dir, test_link_path)
        self.assertEqual(test_link_path, mock_unlink.call_args[0][0])
        self.assertEqual(0, mock_rmdir.call_count)

    @mock.patch('os.listdir', autospec=True)
    @mock.patch('os.rmdir', autospec=True)
    @mock.patch('os.unlink', autospec=True)
    def test_remove_with_dirs(self, mock_unlink, mock_rmdir, mock_listdir):
        """
        This tests removing a symlink that is in some sub-directories of the publishing directory
        """
        # Setup
        test_publish_dir = '/fake/publish/dir'
        test_link_path = '/fake/publish/dir/some/sub/dir/repo'
        mock_listdir.return_value = []

        # Test that the link was removed and mock_rmdir gets called 3 times with the right dir names
        util.remove_repo_publish_dir(test_publish_dir, test_link_path)
        self.assertEqual(test_link_path, mock_unlink.call_args[0][0])
        self.assertEqual(3, mock_rmdir.call_count)
        self.assertEqual('/fake/publish/dir/some/sub/dir', mock_rmdir.call_args_list[0][0][0])
        self.assertEqual('/fake/publish/dir/some/sub', mock_rmdir.call_args_list[1][0][0])
        self.assertEqual('/fake/publish/dir/some', mock_rmdir.call_args_list[2][0][0])

    @mock.patch('os.listdir', autospec=True)
    @mock.patch('os.rmdir', autospec=True)
    @mock.patch('os.unlink', autospec=True)
    def test_remove_with_shared_dirs(self, mock_unlink, mock_rmdir, mock_listdir):
        """
        This tests removing a repo link that shares part of a relative url: rhel6/x86_64/repo and
        rhel6/src/repo for example.
        """
        # Setup
        test_publish_dir = '/fake/publish/dir'
        test_link_path = '/fake/publish/dir/some/dir/repo'
        # Fake returning a list that has items in it
        mock_listdir.return_value = ['second_repo']

        # Test that the symlink is removed and mock_rmdir doesn't get called because listdir returns
        # Something other than an empty list.
        util.remove_repo_publish_dir(test_publish_dir, test_link_path)
        self.assertEqual(test_link_path, mock_unlink.call_args[0][0])
        self.assertEqual(0, mock_rmdir.call_count)
