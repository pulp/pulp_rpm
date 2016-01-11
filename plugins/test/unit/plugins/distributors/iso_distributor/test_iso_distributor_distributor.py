"""
Tests for pulp_rpm.plugins.distributors.iso_distributor.distributor
"""
import os
import shutil
import tempfile
import unittest

from mock import MagicMock, patch
from pulp.devel.mock_distributor import get_basic_config

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.distributors.iso_distributor import distributor


class TestEntryPoint(unittest.TestCase):
    """
    Test the entry_point method. This is really just to get good coverage numbers, but hey.
    """

    def test_entry_point(self):
        iso_distributor, config = distributor.entry_point()
        self.assertEqual(iso_distributor, distributor.ISODistributor)
        self.assertEqual(config, {})


class TestISODistributor(unittest.TestCase):
    """
    Test the ISODistributor object.
    """

    def setUp(self):
        self.iso_distributor = distributor.ISODistributor()
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

    def _get_default_repo(self):
        repo = MagicMock()
        repo.id = 'awesome_repo'
        return repo

    def test_metadata(self):
        metadata = distributor.ISODistributor.metadata()
        self.assertEqual(metadata['id'], ids.TYPE_ID_DISTRIBUTOR_ISO)
        self.assertEqual(metadata['display_name'], 'ISO Distributor')
        self.assertEqual(metadata['types'], [ids.TYPE_ID_ISO])

    def test_validate_config(self):
        # validate_config doesn't use the repo or related_repos args, so we'll just pass None for
        # ease
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                     constants.CONFIG_SERVE_HTTPS: True})
        status, error_message = self.iso_distributor.validate_config(None, config, None)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

        # Try setting the HTTP one to a string, which should be OK as long as it's still True
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: "True",
                                     constants.CONFIG_SERVE_HTTPS: True})
        status, error_message = self.iso_distributor.validate_config(None, config, None)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

        # Now try setting the HTTPS one to an invalid string
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                     constants.CONFIG_SERVE_HTTPS: "Heyo!"})
        status, error_message = self.iso_distributor.validate_config(None, config, None)
        self.assertFalse(status)
        self.assertEqual(error_message,
                         'The configuration parameter <serve_https> may only be set to a '
                         'boolean value, but is currently set to <Heyo!>.')

    def test_get_hosting_locations_http_only(self):
        """
        Test the _get_hosting_locations() for an http only repository function.
        """
        repo = self._get_default_repo()
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                     constants.CONFIG_SERVE_HTTPS: False})
        locations = self.iso_distributor.get_hosting_locations(repo, config)
        self.assertEquals(1, len(locations))
        self.assertEquals(os.path.join(constants.ISO_HTTP_DIR, repo.id), locations[0])

    def test_get_hosting_locations_https_only(self):
        """
        Test the _get_hosting_locations() for an http only repository function.
        """
        repo = self._get_default_repo()
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTPS: True})

        locations = self.iso_distributor.get_hosting_locations(repo, config)
        self.assertEquals(1, len(locations))
        self.assertEquals(os.path.join(constants.ISO_HTTPS_DIR, repo.id), locations[0])

    def test_get_hosting_locations_https_only_default(self):
        """
        Test the _get_hosting_locations() for an http only repository function.
        """
        repo = self._get_default_repo()
        config = get_basic_config()
        locations = self.iso_distributor.get_hosting_locations(repo, config)
        self.assertEquals(1, len(locations))
        self.assertEquals(os.path.join(constants.ISO_HTTPS_DIR, repo.id), locations[0])

    def test_get_hosting_locations_http_and_https(self):
        """
        Test the _get_hosting_locations() for an http only repository function.
        """
        repo = self._get_default_repo()
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                     constants.CONFIG_SERVE_HTTPS: True})
        locations = self.iso_distributor.get_hosting_locations(repo, config)
        self.assertEquals(2, len(locations))
        self.assertEquals(os.path.join(constants.ISO_HTTP_DIR, repo.id), locations[0])
        self.assertEquals(os.path.join(constants.ISO_HTTPS_DIR, repo.id), locations[1])

    @patch(
        'pulp_rpm.plugins.distributors.iso_distributor.distributor.publish'
        '.remove_repository_protection',
        autospec=True)
    def test_distributor_remove_calls_remove_repository_protection(self, mock_publish):
        repo = self._get_default_repo()
        self.iso_distributor.get_hosting_locations = MagicMock()
        self.iso_distributor.get_hosting_locations.return_value = []
        self.iso_distributor.unpublish_repo(repo, {})
        mock_publish.assert_called_once_with(repo.repo_obj)

    @patch(
        'pulp_rpm.plugins.distributors.iso_distributor.distributor.publish'
        '.configure_repository_protection',
        autospec=True)
    def test_post_repo_publish_calls_configure_repository_protection_if_https_enabled(
            self, mock_protection):
        repo = self._get_default_repo()
        cert = "foo"
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: False,
                                     constants.CONFIG_SERVE_HTTPS: True,
                                     constants.CONFIG_SSL_AUTH_CA_CERT: cert})

        self.iso_distributor.post_repo_publish(repo, config)
        mock_protection.assert_called_once_with(repo, cert)

    @patch(
        'pulp_rpm.plugins.distributors.iso_distributor.distributor.publish'
        '.configure_repository_protection',
        autospec=True)
    def test_post_repo_publish_ignores_configure_repository_protection_if_cert_missing(
            self, mock_protection):
        repo = self._get_default_repo()
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: False,
                                     constants.CONFIG_SERVE_HTTPS: True})
        self.iso_distributor.post_repo_publish(repo, config)
        self.assertFalse(mock_protection.called)

    @patch(
        'pulp_rpm.plugins.distributors.iso_distributor.distributor.publish'
        '.configure_repository_protection',
        autospec=True)
    def test_post_repo_publish_does_not_call_configure_repository_protection_if_https_disabled(
            self, mock_protection):
        repo = self._get_default_repo()
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTPS: False})
        self.iso_distributor.post_repo_publish(repo, config)
        self.assertFalse(mock_protection.called)
