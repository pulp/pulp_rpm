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

from ConfigParser import SafeConfigParser
import csv
import errno
import os
import shutil
import tempfile
import unittest

from mock import MagicMock, patch
from pulp.plugins.model import Repository, Unit

from pulp_rpm.common import constants, ids, models, progress
from pulp_rpm.plugins.distributors.iso_distributor import publish
from pulp_rpm.repo_auth.protected_repo_utils import ProtectedRepoUtils
from pulp_rpm.repo_auth.repo_cert_utils import RepoCertUtils
import distributor_mocks



class PublishTests(unittest.TestCase):
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


class TestPublish(PublishTests):
    """
    Test the publish() function.
    """
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
            manifest_filename = os.path.join(publishing_path, models.ISOManifest.FILENAME)
            manifest_rows = []
            with open(manifest_filename) as manifest_file:
                manifest = csv.reader(manifest_file)
                for row in manifest:
                    manifest_rows.append(row)
            expected_manifest_rows = [['test.iso', 'sum1', '1'], ['test2.iso', 'sum2', '2'],
                                      ['test3.iso', 'sum3', '3']]
            self.assertEqual(manifest_rows, expected_manifest_rows)
        delete_protected_repo.assert_called_once_with(repo.id)

        # The publish_conduit should have had two set_progress calls. One to start the IN_PROGRESS
        # state, and the second to mark it as complete
        self.assertEqual(publish_conduit.set_progress.call_count, 2)
        self.assertEqual(publish_conduit.set_progress.mock_calls[0][1][0]['state'],
                         progress.PublishProgressReport.STATE_IN_PROGRESS)
        self.assertEqual(publish_conduit.set_progress.mock_calls[1][1][0]['state'],
                         progress.PublishProgressReport.STATE_COMPLETE)

    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish.unpublish', autospec=True,
           side_effect=publish.unpublish)
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_publish_calls_unpublish(self, delete_protected_repo, unpublish):
        """
        Make sure that the unpublish() function is called during the publish operation, to cleanup what might
        have already been in the publishing location.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=self.existing_units)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})
        publishing_paths = [os.path.join(directory, 'lebowski') \
                            for directory in [constants.ISO_HTTP_DIR, constants.ISO_HTTPS_DIR]]
        # Let's put some junk files in the publishing paths, and make sure that the unpublish step removes them
        delme_filename = 'delme'
        for publishing_path in publishing_paths:
            os.makedirs(publishing_path)
            with open(os.path.join(publishing_path, delme_filename), 'w') as delme:
                delme.write('Deleeeeete meeeeee!')

        report = publish.publish(repo, publish_conduit, config)

        self.assertTrue(report.success_flag)
        self.assertEqual(report.summary['state'], progress.ISOProgressReport.STATE_COMPLETE)
        # Let's verify that the publish directory looks right
        for publishing_path in publishing_paths:
            for unit in self.existing_units:
                expected_symlink_path = os.path.join(publishing_path, unit.unit_key['name'])
                self.assertTrue(os.path.islink(expected_symlink_path))
                expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
                self.assertEqual(os.path.realpath(expected_symlink_path),
                                 expected_symlink_destination)

            # Now let's have a look at the PULP_MANIFEST file to make sure it was generated and
            # published correctly.
            manifest_filename = os.path.join(publishing_path, models.ISOManifest.FILENAME)
            manifest_rows = []
            with open(manifest_filename) as manifest_file:
                manifest = csv.reader(manifest_file)
                for row in manifest:
                    manifest_rows.append(row)
            expected_manifest_rows = [['test.iso', 'sum1', '1'], ['test2.iso', 'sum2', '2'],
                                      ['test3.iso', 'sum3', '3']]
            self.assertEqual(manifest_rows, expected_manifest_rows)
            self.assertFalse(os.path.exists(os.path.join(publishing_path, delme_filename)))
        delete_protected_repo.assert_called_once_with(repo.id)
        unpublish.assert_called_once_with(repo)

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

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_republish_after_unit_removal(self, delete_protected_repo):
        """
        This test checks for an issue[0] we had where publishing an ISO repository, removing an ISO,
        and then republishing would leave that removed ISO's symlink in the repository even though
        it had been removed from the manifest. This test asserts that the republished repository no
        longer contains the removed ISO.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=970795

        :param delete_protected_repo: The mocked version of delete_protected_repo
        :type  delete_protected_repo: function
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=self.existing_units)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})
        # Perform a publish with all of the units in the conduit
        report = publish.publish(repo, publish_conduit, config)
        # Now let's make another conduit that has test2.iso removed
        existing_units = [
            unit for unit in self.existing_units if unit.unit_key['name'] != 'test2.iso']
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=existing_units)
        # Let's reset the delete_protected_repo mock, so we can easily assert that it gets called
        # once more
        delete_protected_repo.reset_mock()

        # Let's republish with our new conduit
        report = publish.publish(repo, publish_conduit, config)

        # Now let's inspect the results
        self.assertTrue(report.success_flag)
        self.assertEqual(report.summary['state'], progress.ISOProgressReport.STATE_COMPLETE)
        # Let's verify that the publish directory looks right
        publishing_paths = [os.path.join(directory, 'lebowski') \
                            for directory in [constants.ISO_HTTP_DIR, constants.ISO_HTTPS_DIR]]
        for publishing_path in publishing_paths:
            for unit in existing_units:
                expected_symlink_path = os.path.join(publishing_path, unit.unit_key['name'])
                self.assertTrue(os.path.islink(expected_symlink_path))
                expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
                self.assertEqual(os.path.realpath(expected_symlink_path),
                                 expected_symlink_destination)
            # Verify that test2.iso is not present
            would_be_symlink_path = os.path.join(publishing_path, 'test2.iso')
            self.assertFalse(os.path.islink(would_be_symlink_path))
            self.assertFalse(os.path.exists(would_be_symlink_path))

            # Now let's have a look at the PULP_MANIFEST file to make sure it was generated and
            # published correctly.
            manifest_filename = os.path.join(publishing_path, models.ISOManifest.FILENAME)
            manifest_rows = []
            with open(manifest_filename) as manifest_file:
                manifest = csv.reader(manifest_file)
                for row in manifest:
                    manifest_rows.append(row)
            # test2.iso should not be present in the manifest either
            expected_manifest_rows = [['test.iso', 'sum1', '1'],
                                      ['test3.iso', 'sum3', '3']]
            self.assertEqual(manifest_rows, expected_manifest_rows)
        delete_protected_repo.assert_called_once_with(repo.id)

        # The publish_conduit should have had two set_progress calls. One to start the IN_PROGRESS
        # state, and the second to mark it as complete
        self.assertEqual(publish_conduit.set_progress.call_count, 2)
        self.assertEqual(publish_conduit.set_progress.mock_calls[0][1][0]['state'],
                         progress.PublishProgressReport.STATE_IN_PROGRESS)
        self.assertEqual(publish_conduit.set_progress.mock_calls[1][1][0]['state'],
                         progress.PublishProgressReport.STATE_COMPLETE)


class TestUnpublish(PublishTests):
    """
    Test the unpublish() method.
    """
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_unpublish(self, delete_protected_repo):
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        publishing_paths = publish._get_hosting_locations(repo)
        # Let's put some junk files in the publishing paths, and make sure that the unpublish step removes them
        delme_filename = 'delme'
        for publishing_path in publishing_paths:
            os.makedirs(publishing_path)
            with open(os.path.join(publishing_path, delme_filename), 'w') as delme:
                delme.write('Deleeeeete meeeeee!')

        publish.unpublish(repo)

        # Let's verify that the publish directories are gone
        for path in publish._get_hosting_locations(repo):
            self.assertFalse(os.path.exists(path))
        delete_protected_repo.assert_called_once_with(publish._get_relative_path(repo))


class TestBuildMetadata(PublishTests):
    """
    Test the _build_metadata() function.
    """
    def test__build_metadata(self):
        """
        The _build_metadata() method should put the metadata in the build directory.
        """
        build_dir = self.temp_dir

        publish._build_metadata(build_dir, self.existing_units)

        # Now let's have a look at the PULP_MANIFEST file to make sure it was generated correctly.
        manifest_filename = os.path.join(build_dir, models.ISOManifest.FILENAME)
        manifest_rows = []
        with open(manifest_filename) as manifest_file:
            manifest = csv.reader(manifest_file)
            for row in manifest:
                manifest_rows.append(row)
        expected_manifest_rows = [['test.iso', 'sum1', '1'], ['test2.iso', 'sum2', '2'],
                                  ['test3.iso', 'sum3', '3']]
        self.assertEqual(manifest_rows, expected_manifest_rows)


class TestConfigureRepositoryProtection(unittest.TestCase):
    """
    Test the _configure_repository_protection() function.
    """
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.add_protected_repo')
    @patch('pulp_rpm.repo_auth.repo_cert_utils.RepoCertUtils.write_consumer_cert_bundle')
    def test__configure_repository_protection(self, write_consumer_cert_bundle, add_protected_repo):
        repo = MagicMock()
        repo.id = 7
        cert = 'This is a real cert, trust me.'

        publish._configure_repository_protection(repo, cert)

        # Assert that the appropriate repository protection calls were made
        write_consumer_cert_bundle.assert_called_once_with(repo.id, {'ca': cert})
        add_protected_repo.assert_called_once_with(publish._get_relative_path(repo), repo.id)


class TestCopyToHostedLocation(PublishTests):
    """
    Test the _copy_to_hosted_location() function.
    """
    def test__copy_to_hosted_location(self):
        """
        Test the operation of _copy_to_hosted_location().
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})

        # Let's make the build_dir and put a dummy file and a dummy symlink in it, so we can make
        # sure they get copied to the right places.
        build_dir = os.path.join(repo.working_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should copy our dummy file to the monkey patched folders from our setUp() method.
        publish._copy_to_hosted_location(repo, config, build_dir)

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

    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish._configure_repository_protection',
           side_effect=publish._configure_repository_protection, autospec=True)
    def test__copy_to_hosted_location_https_false_doesnt_protect_repo(self, _configure_repository_protection):
        """
        Test _copy_to_hosted_location() when CONFIG_SERVE_HTTPS is False. The repo protection code
        should not get called in this case.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: False})
        build_dir = os.path.join(repo.working_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        publish._copy_to_hosted_location(repo, config, build_dir)

        # Since HTTPS publishing was False, we should not call to protect the repository
        self.assertEqual(_configure_repository_protection.call_count, 0)

    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish._configure_repository_protection',
           side_effect=publish._configure_repository_protection, autospec=True)
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.add_protected_repo', autospec=True)
    @patch('pulp_rpm.repo_auth.repo_cert_utils.RepoCertUtils.write_consumer_cert_bundle', autospec=True)
    def test__copy_to_hosted_location_https_true_with_ca_protects_repo(
            self, write_consumer_cert_bundle, add_protected_repo, _configure_repository_protection):
        """
        Test _copy_to_hosted_location() when CONFIG_SERVE_HTTPS is True and a CA is provided. The repo
        protection code should be called.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        cert = 'Only Allow Cool People'
        config = distributor_mocks.get_basic_config(
            **{constants.CONFIG_SERVE_HTTP: True, constants.CONFIG_SERVE_HTTPS: True,
               constants.CONFIG_SSL_AUTH_CA_CERT: cert})
        build_dir = os.path.join(repo.working_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        publish._copy_to_hosted_location(repo, config, build_dir)

        # Assert that _protect_repository was called with the correct parameters
        _configure_repository_protection.assert_called_once_with(repo, cert)

    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish._configure_repository_protection')
    def test__copy_to_hosted_location_https_true_without_ca_doesnt_protect_repo(
            self, _configure_repository_protection):
        """
        Test _copy_to_hosted_location() when CONFIG_SERVE_HTTPS is True, but no CA is provided. The repo
        protection code should not be called.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(
            **{constants.CONFIG_SERVE_HTTP: True, constants.CONFIG_SERVE_HTTPS: True})
        build_dir = os.path.join(repo.working_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        publish._copy_to_hosted_location(repo, config, build_dir)

        # Assert that _protect_repository was not called
        self.assertEqual(_configure_repository_protection.call_count, 0)

    def test__copy_to_hosted_location_serve_http_default(self):
        """
        Assert that we don't publish over HTTP by default.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTPS: False})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = os.path.join(repo.working_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should not copy our dummy file anywhere.
        publish._copy_to_hosted_location(repo, config, build_dir)

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

    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish._configure_repository_protection')
    def test__copy_to_hosted_location_serve_https_default(self, _configure_repository_protection):
        """
        Assert that we do publish over HTTPS by default.
        """
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: False})

        # Let's put a dummy file and a dummy symlink in the build_dir, so we can make sure they get
        # copied to the right places.
        build_dir = os.path.join(repo.working_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        with open(os.path.join(build_dir, 'the_dude.txt'), 'w') as the_dude:
            the_dude.write("Let's go bowling.")
        os.symlink('/symlink/path', os.path.join(build_dir, 'symlink'))

        # This should copy our dummy file to the monkey patched folders from our setUp() method.
        publish._copy_to_hosted_location(repo, config, build_dir)

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

        # Since there's no CA cert, the repo should not be protected
        self.assertEqual(_configure_repository_protection.call_count, 0)


class TestGetHostingLocations(unittest.TestCase):
    """
    Test the _get_hosting_locations() function.
    """
    def test__get_hosting_locations(self):
        repo = MagicMock()
        repo.id = 'awesome_repo'

        http_dir, https_dir = publish._get_hosting_locations(repo)

        self.assertEqual(http_dir, os.path.join(constants.ISO_HTTP_DIR, repo.id))
        self.assertEqual(https_dir, os.path.join(constants.ISO_HTTPS_DIR, repo.id))


class TestGetRelativePath(unittest.TestCase):
    """
    Test the _get_relative_path() function.
    """
    def test__get_relative_path(self):
        repo = MagicMock()
        repo.id = 'awesome_repo'

        relative_path = publish._get_relative_path(repo)

        self.assertEqual(relative_path, repo.id)


class TestGetRepositoryProtectionUtils(unittest.TestCase):
    """
    Test the _get_repository_protection_utils() function.
    """
    @patch('pulp_rpm.plugins.distributors.iso_distributor.publish.SafeConfigParser', autospec=True)
    def test__get_repository_protection_utils(self, safe_config_parser_constructor):
        safe_config_parser_constructor = MagicMock

        repo_cert_utils, protected_repo_utils = publish._get_repository_protection_utils()

        repo_auth_config = repo_cert_utils.config
        self.assertTrue(isinstance(repo_auth_config, SafeConfigParser))
        repo_auth_config.read.assert_called_once_with(constants.REPO_AUTH_CONFIG_FILE)

        self.assertTrue(isinstance(repo_cert_utils, RepoCertUtils))
        self.assertTrue(isinstance(protected_repo_utils, ProtectedRepoUtils))
        self.assertEqual(protected_repo_utils.config, repo_auth_config)


class TestRemoveRepositoryProtection(unittest.TestCase):
    """
    Test the _remove_repository_protection() function.
    """
    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test__remove_repository_protection(self, delete_protected_repo):
        repo = MagicMock()
        repo.id = 'reporeporeporepo'

        publish._remove_repository_protection(repo)

        delete_protected_repo.assert_called_once_with(publish._get_relative_path(repo))


class TestSymlinkUnits(PublishTests):
    """
    Test the _symlink_units() function.
    """
    def test__symlink_units(self):
        """
        Make sure that the _symlink_units creates all the correct symlinks.
        """
        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = os.path.join(self.temp_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        os.symlink('/some/weird/path',
                   os.path.join(build_dir, self.existing_units[0].unit_key['name']))
        with open(os.path.join(build_dir, self.existing_units[1].unit_key['name']), 'w') as wrong:
            wrong.write("This is wrong.")

        publish._symlink_units(build_dir, self.existing_units)

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
        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = os.path.join(self.temp_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        unit = self.existing_units[0]
        expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
        os.symlink(expected_symlink_destination,
                   os.path.join(build_dir, unit.unit_key['name']))
        # Now let's reset the Mock so that we can make sure it doesn't get called during _symlink
        symlink.reset_mock()

        publish._symlink_units(build_dir, [unit])

        # The call count for symlink should be 0, because the _symlink_units call should have
        # noticed that the symlink was already correct and thus should have skipped it
        self.assertEqual(symlink.call_count, 0)
        expected_symlink_path = os.path.join(build_dir, unit.unit_key['name'])
        self.assertTrue(os.path.islink(expected_symlink_path))
        self.assertEqual(os.path.realpath(expected_symlink_path), expected_symlink_destination)

    @patch('os.readlink')
    def test__symlink_units_os_error(self, readlink):
        """
        Make sure that the _symlink_units handles an OSError correctly, for the case where it
        doesn't raise EINVAL. We already have a test that raises EINVAL (test__symlink_units places
        an ordinary file there.)
        """
        os_error = OSError()
        # This would be an unexpected error for reading a symlink!
        os_error.errno = errno.ENOSPC
        readlink.side_effect = os_error
        # There's some logic in _symlink_units to handle preexisting files and symlinks, so let's
        # create some fakes to see if it does the right thing
        build_dir = os.path.join(self.temp_dir, publish.BUILD_DIRNAME)
        os.makedirs(build_dir)
        unit = self.existing_units[0]
        expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
        os.symlink(expected_symlink_destination,
                   os.path.join(build_dir, unit.unit_key['name']))

        try:
            publish._symlink_units(build_dir, [unit])
            self.fail('An OSError should have been raised, but was not!')
        except OSError, e:
            self.assertEqual(e.errno, errno.ENOSPC)


class TestRMTreeIfExists(PublishTests):
    """
    Test the _rmtree_if_exists() function.
    """
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
