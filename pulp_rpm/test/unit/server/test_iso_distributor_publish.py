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
import csv
import os
import shutil
import tempfile

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.distributors.iso_distributor import publish
from rpm_support_base import PulpRPMTests
import importer_mocks
import distributor_mocks

from mock import call, MagicMock, patch
from pulp.plugins.model import Repository, Unit

class TestPublish(PulpRPMTests):
    """
    Test the publish module.
    """
    def setUp(self):
        self.existing_units = [
            Unit(ids.TYPE_ID_ISO, {'name': 'test.iso', 'size': 1, 'checksum': 'sum1'},
                 {}, '/path/test.iso'),
            Unit(ids.TYPE_ID_ISO,{'name': 'test2.iso', 'size': 2, 'checksum': 'sum2'},
                 {}, '/path/test2.iso'),
            Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso', 'size': 3, 'checksum': 'sum3'},
                 {}, '/path/test3.iso')]
        self.publish_conduit = distributor_mocks.get_publish_conduit(
            existing_units=self.existing_units)
        self.temp_dir = tempfile.mkdtemp()

        # Monkeypatch the publishing location so we don't try to write to /var
        self._original_iso_http_dir = constants.ISO_HTTP_DIR
        self._original_iso_https_dir = constants.ISO_HTTPS_DIR
        constants.ISO_HTTP_DIR = os.path.join(self.temp_dir, 'published', 'http', 'isos')
        constants.ISO_HTTPS_DIR = os.path.join(self.temp_dir, 'published', 'https', 'isos')

    def tearDown(self):
        # Undo our monkeypatch and clean up our temp dir
        constants.ISO_HTTP_DIR = self._original_iso_http_dir
        constants.ISO_HTTPS_DIR = self._original_iso_https_dir
        shutil.rmtree(self.temp_dir)

    def test__build_metadata(self):
        """
        The _build_metadata() method should put the metadata in the build directory.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir
        publish._build_metadata(repo, self.existing_units)

        # Now let's have a look at the PULP_MANIFEST file to make sure it was generated correctly.
        manifest_filename = os.path.join(self.temp_dir, publish.BUILD_DIRNAME,
                                constants.ISO_MANIFEST_FILENAME)
        manifest_rows = []
        with open(manifest_filename) as manifest_file:
            manifest = csv.reader(manifest_file)
            for row in manifest:
                manifest_rows.append(row)
        expected_manifest_rows = [['test.iso', 'sum1', '1'], ['test2.iso', 'sum2', '2'],
                                  ['test3.iso', 'sum3', '3']]
        self.assertEqual(manifest_rows, expected_manifest_rows)

    def test__copy_to_hosted_location(self):
        """
        Test the operation of _copy_to_hosted_location().
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = publish._get_or_create_build_dir(repo)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should copy our dummy file to the monkey patched folders from our setUp() method.
        publish._copy_to_hosted_location(repo, config)

        # Make sure that the_dude.txt got copied to the right places
        expected_http_path = os.path.join(constants.ISO_HTTP_DIR, 'lebowski', 'the_dude.txt')
        expected_https_path = os.path.join(constants.ISO_HTTPS_DIR, 'lebowski', 'the_dude.txt')
        self.assertTrue(os.path.exists(expected_http_path))
        self.assertTrue(os.path.exists(expected_https_path))
        # Now make sure our symlink is also in place, and points to the correct location
        expected_http_symlink_path = os.path.join(constants.ISO_HTTP_DIR, 'lebowski', 'symlink')
        expected_https_symlink_path = os.path.join(constants.ISO_HTTPS_DIR, 'lebowski', 'symlink')
        self.assertTrue(os.path.islink(expected_http_symlink_path))
        self.assertTrue(os.path.islink(expected_https_symlink_path))
        self.assertEqual(os.path.realpath(expected_http_symlink_path), '/symlink/path')
        self.assertEqual(os.path.realpath(expected_https_symlink_path), '/symlink/path')

    def test__get_or_create_build_dir(self):
        """
        _get_or_create_build_dir() should create the directory the first time it is called, and
        should return the path to it both times it is called.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir

        # Assert that the build dir does not exist
        expected_build_dir = os.path.join(self.temp_dir, publish.BUILD_DIRNAME)
        self.assertFalse(os.path.exists(expected_build_dir))

        build_dir = publish._get_or_create_build_dir(repo)

        # Assert that the build dir is correct and has been created
        self.assertEqual(build_dir, expected_build_dir)
        self.assertTrue(os.path.exists(build_dir))

    def test__symlink_units(self):
        """
        Make sure that the _symlink_units creates all the correct symlinks.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir

        publish._symlink_units(repo, self.existing_units)

        build_dir = publish._get_or_create_build_dir(repo)
        for unit in self.existing_units:
            expected_symlink_path = os.path.join(build_dir, unit.unit_key['name'])
            self.assertTrue(os.path.islink(expected_symlink_path))
            expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
            self.assertEqual(os.path.realpath(expected_symlink_path), expected_symlink_destination)

    def test__rmtree_if_exists(self):
        """
        Let's just make sure this simple thing doesn't barf.
        """
        a_directory = os.path.join(self.temp_dir, 'a_directory')
        test_filename = os.path.join(a_directory, 'test.txt')
        os.makedirs(a_directory)
        with open(test_filename, 'w') as test:
            test.write("Please don't barf.")

        # This should not cause any problems, and test.txt should still exist
        publish._rmtree_if_exists(os.path.join(self.temp_dir, 'fake_path'))
        self.assertTrue(os.path.exists(test_filename))

        # Now let's remove a_directory
        publish._rmtree_if_exists(a_directory)
        self.assertFalse(os.path.exists(a_directory))
