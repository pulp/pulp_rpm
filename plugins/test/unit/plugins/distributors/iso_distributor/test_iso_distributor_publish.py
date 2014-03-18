from ConfigParser import SafeConfigParser
import os
import shutil
import tempfile
import unittest

from mock import MagicMock, patch
from pulp.plugins.model import Unit
from pulp.devel.mock_distributor import get_publish_conduit

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.distributors.iso_distributor import publish
from pulp_rpm.repo_auth.protected_repo_utils import ProtectedRepoUtils
from pulp_rpm.repo_auth.repo_cert_utils import RepoCertUtils


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.existing_units = [
            Unit(ids.TYPE_ID_ISO, {'name': 'test.iso', 'size': 1, 'checksum': 'sum1'},
                 {}, '/path/test.iso'),
            Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso', 'size': 2, 'checksum': 'sum2'},
                 {}, '/path/test2.iso'),
            Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso', 'size': 3, 'checksum': 'sum3'},
                 {}, '/path/test3.iso')]
        self.publish_conduit = get_publish_conduit(
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

        publish.configure_repository_protection(repo, cert)

        # Assert that the appropriate repository protection calls were made
        write_consumer_cert_bundle.assert_called_once_with(repo.id, {'ca': cert})
        add_protected_repo.assert_called_once_with(publish._get_relative_path(repo), repo.id)

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

        publish.remove_repository_protection(repo)

        delete_protected_repo.assert_called_once_with(publish._get_relative_path(repo))
