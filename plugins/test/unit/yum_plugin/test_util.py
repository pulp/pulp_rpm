# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import unittest

from pulp_rpm.devel import rpm_support_base
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
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                     "../../../../pulp_rpm/test/unit/server/data"))

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def test_is_rpm_newer(self):
        rpm_a = {"name": "rpm_test_name", "epoch": "0", "release": "el6.1", "version": "2",
                 "arch": "noarch"}
        newer_a = {"name": "rpm_test_name", "epoch": "0", "release": "el6.1", "version": "3",
                   "arch": "noarch"}
        newer_a_diff_arch = {"name": "rpm_test_name", "epoch": "0", "release": "el6.1",
                             "version": "2", "arch": "i386"}
        rpm_b = {"name": "rpm_test_name_B", "epoch": "0", "release": "el6.1", "version": "5",
                 "arch": "noarch"}

        self.assertTrue(util.is_rpm_newer(newer_a, rpm_a))
        self.assertFalse(util.is_rpm_newer(newer_a_diff_arch, rpm_a))
        self.assertFalse(util.is_rpm_newer(rpm_a, newer_a))
        self.assertFalse(util.is_rpm_newer(newer_a, rpm_b))


class TestGenerateListingFiles(unittest.TestCase):
    def test_repo_dir_not_descendant(self):
        self.assertRaises(ValueError, util.generate_listing_files, '/a/b/c', '/d/e/f')

    def test_all(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            # setup a directory structure and define the expected listing file values
            publish_dir = os.path.join(tmp_dir, 'a/b/c')
            os.makedirs(publish_dir)
            os.makedirs(os.path.join(tmp_dir, 'a/d'))
            os.makedirs(os.path.join(tmp_dir, 'a/b/e'))
            expected = ['a', 'b\nd', 'c\ne']

            # run it
            util.generate_listing_files(tmp_dir, publish_dir)

            # ensure that each listing file exists and has the correct contents
            current_path = tmp_dir
            for next_dir, expected_listing in zip(['a', 'b', 'c'], expected):
                file_path = os.path.join(current_path, 'listing')
                with open(file_path) as open_file:
                    self.assertEqual(open_file.read(), expected_listing)
                current_path = os.path.join(current_path, next_dir)

            # make sure there is not a listing file inside the repo's publish dir
            self.assertFalse(os.path.exists(os.path.join(publish_dir, 'listing')))

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
