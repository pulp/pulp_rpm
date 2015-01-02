# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import unittest

from pulp.plugins.model import Unit
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


class TestRelativePath(unittest.TestCase):
    def test_get_relpath_from_unit(self):
        unit = Unit(type_id='random',
                    unit_key={"filename": "test_unit_key_filename"},
                    metadata={"filename": "test_metadata_filename"},
                    storage_path="/test/storage/path")
        self.assertEqual(util.get_relpath_from_unit(unit), "test_metadata_filename")
        unit = Unit(type_id='random',
                    unit_key={"filename": "test_unit_key_filename"},
                    metadata={},
                    storage_path="/test/storage/path")
        self.assertEqual(util.get_relpath_from_unit(unit), "test_unit_key_filename")
        unit = Unit(type_id='random',
                    unit_key={"fileName": "test_unit_key_fileName"},
                    metadata={},
                    storage_path="/test/storage/path")
        self.assertEqual(util.get_relpath_from_unit(unit), "test_unit_key_fileName")
        unit = Unit(type_id='random',
                    unit_key={},
                    metadata={},
                    storage_path="/test/storage/path")
        self.assertEqual(util.get_relpath_from_unit(unit), "path")


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
