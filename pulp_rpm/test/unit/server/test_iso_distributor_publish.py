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


class TestProtectRepository(PulpRPMTests):
    """
    Test the _protect_repository() function.
    """
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.add_protected_repo')
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    @patch('pulp_rpm.repo_auth.repo_cert_utils.RepoCertUtils.write_consumer_cert_bundle')
    def test_with_auth_cert(self, write_consumer_cert_bundle, delete_protected_repo, add_protected_repo):
        """
        Test behavior when an auth cert is provided.
        """
        relative_path = 'relative/path'
        repo = MagicMock()
        repo.id = 7
        cert = 'This is a real cert, trust me.'
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SSL_AUTH_CA_CERT: cert})

        publish._protect_repository(relative_path, repo, config)

        # Assert that the appropriate repository protection calls were made
        write_consumer_cert_bundle.assert_called_once_with(repo.id, {'ca': cert})
        add_protected_repo.assert_called_once_with(relative_path, repo.id)
        self.assertEqual(delete_protected_repo.call_count, 0)

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.add_protected_repo')
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    @patch('pulp_rpm.repo_auth.repo_cert_utils.RepoCertUtils.write_consumer_cert_bundle')
    def test_without_auth_cert(self, write_consumer_cert_bundle, delete_protected_repo, add_protected_repo):
        """
        Test behavior when no auth cert is provided.
        """
        relative_path = 'relative/path'
        repo = MagicMock()
        repo.id = 7
        config = distributor_mocks.get_basic_config()

        publish._protect_repository(relative_path, repo, config)

        # Assert that the repository protection removal call was made, and not the protection establishment
        # calls
        self.assertEqual(write_consumer_cert_bundle.call_count, 0)
        self.assertEqual(add_protected_repo.call_count, 0)
        delete_protected_repo.assert_called_once_with(relative_path)


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

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_publish(self, delete_protected_repo):
        """
        Test the publish method.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=self.existing_units)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})
        report = publish.publish(repo, publish_conduit, config)

        self.assertTrue(report.success_flag)
        self.assertEqual(report.summary['state'], progress.ISOProgressReport.STATE_COMPLETE)
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
        delete_protected_repo.assert_called_once_with(repo.id)

        # The publish_conduit should have had two set_progress calls. One to start the IN_PROGRESS state, and
        # the second to mark it as complete
        self.assertEqual(publish_conduit.set_progress.call_count, 2)
        self.assertEqual(publish_conduit.set_progress.mock_calls[0][1][0]['state'],
                         progress.PublishProgressReport.STATE_IN_PROGRESS)
        self.assertEqual(publish_conduit.set_progress.mock_calls[1][1][0]['state'],
                         progress.PublishProgressReport.STATE_COMPLETE)

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_publish_handles_errors(self, delete_protected_repo):
        """
        Make sure that publish() does the right thing with the report when there is an error.
        """
        delete_protected_repo.side_effect=Exception('Rawr!')
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=self.existing_units)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})

        report = publish.publish(repo, publish_conduit, config)

        self.assertFalse(report.success_flag)
        self.assertEqual(report.summary['state'], progress.ISOProgressReport.STATE_FAILED)
        self.assertEqual(report.summary['error_message'], 'Rawr!')
        self.assertTrue('Rawr!' in report.summary['traceback'])

        # The publish_conduit should have had two set_progress calls. One to start the IN_PROGRESS state, and
        # the second to mark it as failed
        self.assertEqual(publish_conduit.set_progress.call_count, 2)
        self.assertEqual(publish_conduit.set_progress.mock_calls[0][1][0]['state'],
                         progress.PublishProgressReport.STATE_IN_PROGRESS)
        self.assertEqual(publish_conduit.set_progress.mock_calls[1][1][0]['state'],
                         progress.PublishProgressReport.STATE_FAILED)

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

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test__copy_to_hosted_location(self, delete_protected_repo):
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

        # delete_protected_repo should have been called since there's no CA cert provided
        delete_protected_repo.assert_called_once_with(repo.id)

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish._protect_repository',
           side_effect=publish._protect_repository)
    def test__copy_to_hosted_location_https_false_doesnt_protect_repo(self, _protect_repository,
                                                                      delete_protected_repo):
        """
        Test _copy_to_hosted_location() when CONFIG_SERVE_HTTPS is False. The repo protection code should get
        called in this case, and should cause the delete_protected_repo() to get used.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: False})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = publish._get_or_create_build_dir(repo)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should copy our dummy file to the monkey patched folders from our setUp() method.
        publish._copy_to_hosted_location(repo, config)

        # Even though HTTPS publishing was False, we should still call to protect the repository
        _protect_repository.assert_called_once_with(repo.id, repo, config)
        delete_protected_repo.assert_called_once_with(repo.id)

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish._protect_repository',
           side_effect=publish._protect_repository)
    def test__copy_to_hosted_location_https_true_protects_repo(self, _protect_repository,
                                                               delete_protected_repo):
        """
        Test _copy_to_hosted_location() when CONFIG_SERVE_HTTPS is True. The repo protection code should be
        called.
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

        # Assert that _protect_repository was called with the correct parameters
        _protect_repository.assert_called_once_with(repo.id, repo, config)
        # Assert correct call to delete_protected_repo since there was no CA cert provided
        delete_protected_repo.assert_called_once_with(repo.id)

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test__copy_to_hosted_location_serve_http_default(self, delete_protected_repo):
        """
        Assert that we don't publish over HTTP by default.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTPS: False})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = publish._get_or_create_build_dir(repo)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should not copy our dummy file anywhere.
        publish._copy_to_hosted_location(repo, config)

        # Make sure that the_dude.txt didn't get copied
        expected_http_path = os.path.join(constants.ISO_HTTP_DIR, 'lebowski', 'the_dude.txt')
        expected_https_path = os.path.join(constants.ISO_HTTPS_DIR, 'lebowski', 'the_dude.txt')
        self.assertFalse(os.path.exists(expected_http_path))
        self.assertFalse(os.path.exists(expected_https_path))
        # Now make sure our symlink isn't in place
        expected_http_symlink_path = os.path.join(constants.ISO_HTTP_DIR, 'lebowski', 'symlink')
        expected_https_symlink_path = os.path.join(constants.ISO_HTTPS_DIR, 'lebowski', 'symlink')
        self.assertFalse(os.path.islink(expected_http_symlink_path))
        self.assertFalse(os.path.islink(expected_https_symlink_path))

        # delete_protected_repo should have been called since there's no CA cert provided
        delete_protected_repo.assert_called_once_with(repo.id)

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test__copy_to_hosted_location_serve_https_default(self, delete_protected_repo):
        """
        Assert that we do publish over HTTPS by default.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: False})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = publish._get_or_create_build_dir(repo)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should copy our dummy file to the monkey patched folders from our setUp() method.
        publish._copy_to_hosted_location(repo, config)

        # Make sure that the_dude.txt got copied to the HTTPS places and not the HTTP places
        expected_http_path = os.path.join(constants.ISO_HTTP_DIR, 'lebowski', 'the_dude.txt')
        expected_https_path = os.path.join(constants.ISO_HTTPS_DIR, 'lebowski', 'the_dude.txt')
        self.assertFalse(os.path.exists(expected_http_path))
        self.assertTrue(os.path.exists(expected_https_path))
        # Now make sure our symlink is also in place, and points to the correct location
        expected_http_symlink_path = os.path.join(constants.ISO_HTTP_DIR, 'lebowski', 'symlink')
        expected_https_symlink_path = os.path.join(constants.ISO_HTTPS_DIR, 'lebowski', 'symlink')
        self.assertFalse(os.path.islink(expected_http_symlink_path))
        self.assertTrue(os.path.islink(expected_https_symlink_path))
        self.assertEqual(os.path.realpath(expected_https_symlink_path), '/symlink/path')

        # delete_protected_repo should have been called since there's no CA cert provided
        delete_protected_repo.assert_called_once_with(repo.id)

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

        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = publish._get_or_create_build_dir(repo)
        os.symlink('/some/weird/path',
                   os.path.join(build_dir, self.existing_units[0].unit_key['name']))
        with open(os.path.join(build_dir, self.existing_units[1].unit_key['name']), 'w') as wrong:
            wrong.write("This is wrong.")

        publish._symlink_units(repo, self.existing_units)

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

        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = publish._get_or_create_build_dir(repo)
        unit = self.existing_units[0]
        expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
        os.symlink(expected_symlink_destination,
                   os.path.join(build_dir, unit.unit_key['name']))
        # Now let's reset the Mock so that we can make sure it doesn't get called during _symlink
        symlink.reset_mock()

        publish._symlink_units(repo, [unit])

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

        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = publish._get_or_create_build_dir(repo)
        unit = self.existing_units[0]
        expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
        os.symlink(expected_symlink_destination,
                   os.path.join(build_dir, unit.unit_key['name']))

        try:
            publish._symlink_units(repo, [unit])
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
