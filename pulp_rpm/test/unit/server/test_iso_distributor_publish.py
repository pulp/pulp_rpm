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
import errno
import os
import shutil
import tempfile

from pulp_rpm.common import constants, ids, progress
from pulp_rpm.plugins.distributors.iso_distributor import publish
from rpm_support_base import PulpRPMTests
import distributor_mocks

from mock import MagicMock, patch
from pulp.plugins.model import Repository, Unit


class TestPublish(PulpRPMTests):
    """
    Test the publish module.
    """
    def setUp(self):
        self.existing_units = [
            Unit(ids.TYPE_ID_ISO, {'name': 'test.iso', 'size': 1, 'checksum': 'sum1'},
                 {}, '/path/test.iso'),
            Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso', 'size': 2, 'checksum': 'sum2'},
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

    def test_publish(self):
        """
        Test the publish method.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=self.existing_units)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})
        # We haven't implemented reporting yet, so we don't yet assert anything about the report
        # here.
        report = publish.publish(repo, publish_conduit, config)

        # Let's verify that the publish directory looks right
        publishing_paths = [os.path.join(directory, 'lebowski') \
                            for directory in [constants.ISO_HTTP_DIR, constants.ISO_HTTPS_DIR]]
        for publishing_path in publishing_paths:
            for unit in self.existing_units:
                expected_symlink_path = os.path.join(publishing_path, unit.unit_key['name'])
                self.assertTrue(os.path.islink(expected_symlink_path))
                expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
                self.assertEqual(os.path.realpath(expected_symlink_path),
                                 expected_symlink_destination)

            # Now let's have a look at the PULP_MANIFEST file to make sure it was generated and
            # published correctly.
            manifest_filename = os.path.join(publishing_path, constants.ISO_MANIFEST_FILENAME)
            manifest_rows = []
            with open(manifest_filename) as manifest_file:
                manifest = csv.reader(manifest_file)
                for row in manifest:
                    manifest_rows.append(row)
            expected_manifest_rows = [['test.iso', 'sum1', '1'], ['test2.iso', 'sum2', '2'],
                                      ['test3.iso', 'sum3', '3']]
            self.assertEqual(manifest_rows, expected_manifest_rows)

    def test__build_metadata(self):
        """
        The _build_metadata() method should put the metadata in the build directory.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir
        progress_report = progress.PublishProgressReport(self.publish_conduit)

        publish._build_metadata(repo, self.existing_units, progress_report)

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
        progress_report = progress.PublishProgressReport(self.publish_conduit)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = publish._get_or_create_build_dir(repo)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should copy our dummy file to the monkey patched folders from our setUp() method.
        publish._copy_to_hosted_location(repo, config, progress_report)

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

        # It should not blow up if we call it again
        build_dir = publish._get_or_create_build_dir(repo)
        self.assertEqual(build_dir, expected_build_dir)

    def test__get_or_create_build_dir_already_exists(self):
        """
        _get_or_create_build_dir() should correctly handle the situation when the build_dir already exists.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir

        # Assert that the build dir does not exist
        expected_build_dir = os.path.join(self.temp_dir, publish.BUILD_DIRNAME)
        os.makedirs(expected_build_dir)
        self.assertTrue(os.path.exists(expected_build_dir))

        build_dir = publish._get_or_create_build_dir(repo)

        # Assert that the build dir is correct and has been created
        self.assertEqual(build_dir, expected_build_dir)
        self.assertTrue(os.path.exists(build_dir))

    @patch("os.makedirs")
    def test__get_or_create_build_dir_oserror(self, makedirs):
        """
        Let's raise the OSError that this method tries to catch to make sure we raise it appropriately.
        """
        os_error = OSError()
        os_error.errno = errno.ENOSPC
        makedirs.side_effect = os_error

        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir

        # Assert that the build dir does not exist
        expected_build_dir = os.path.join(self.temp_dir, publish.BUILD_DIRNAME)
        self.assertFalse(os.path.exists(expected_build_dir))

        try:
            publish._get_or_create_build_dir(repo)
            self.fail("An OSError should have been raised but was not.")
        except OSError, e:
            self.assertEqual(e.errno, errno.ENOSPC)

    def test__symlink_units(self):
        """
        Make sure that the _symlink_units creates all the correct symlinks.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir
        progress_report = progress.PublishProgressReport(self.publish_conduit)

        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = publish._get_or_create_build_dir(repo)
        os.symlink('/some/weird/path',
                   os.path.join(build_dir, self.existing_units[0].unit_key['name']))
        with open(os.path.join(build_dir, self.existing_units[1].unit_key['name']), 'w') as wrong:
            wrong.write("This is wrong.")

        publish._symlink_units(repo, self.existing_units, progress_report)

        build_dir = publish._get_or_create_build_dir(repo)
        for unit in self.existing_units:
            expected_symlink_path = os.path.join(build_dir, unit.unit_key['name'])
            self.assertTrue(os.path.islink(expected_symlink_path))
            expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
            self.assertEqual(os.path.realpath(expected_symlink_path), expected_symlink_destination)

    @patch('os.symlink', side_effect=os.symlink)
    def test__symlink_units_existing_correct_link(self, symlink):
        """
        Make sure that the _symlink_units handles an existing correct link well.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir
        progress_report = progress.PublishProgressReport(self.publish_conduit)

        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = publish._get_or_create_build_dir(repo)
        unit = self.existing_units[0]
        expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
        os.symlink(expected_symlink_destination,
                   os.path.join(build_dir, unit.unit_key['name']))
        # Now let's reset the Mock so that we can make sure it doesn't get called during _symlink
        symlink.reset_mock()

        publish._symlink_units(repo, [unit], progress_report)

        # The call count for symlink should be 0, because the _symlink_units call should have noticed that the
        # symlink was already correct and thus should have skipped it
        self.assertEqual(symlink.call_count, 0)
        expected_symlink_path = os.path.join(build_dir, unit.unit_key['name'])
        self.assertTrue(os.path.islink(expected_symlink_path))
        self.assertEqual(os.path.realpath(expected_symlink_path), expected_symlink_destination)

    @patch('os.readlink')
    def test__symlink_units_os_error(self, readlink):
        """
        Make sure that the _symlink_units handles an OSError correctly, for the case where it doesn't raise
        EINVAL. We already have a test that raises EINVAL (test__symlink_units places an ordinary file there.)
        """
        os_error = OSError()
        # This would be an unexpected error for reading a symlink!
        os_error.errno = errno.ENOSPC
        readlink.side_effect = os_error

        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir
        progress_report = progress.PublishProgressReport(self.publish_conduit)

        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = publish._get_or_create_build_dir(repo)
        unit = self.existing_units[0]
        expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
        os.symlink(expected_symlink_destination,
                   os.path.join(build_dir, unit.unit_key['name']))

        try:
            publish._symlink_units(repo, [unit], progress_report)
            self.fail('An OSError should have been raised, but was not!')
        except OSError, e:
            self.assertEqual(e.errno, errno.ENOSPC)

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
