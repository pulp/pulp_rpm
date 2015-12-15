import ConfigParser
import errno
import os
import shutil
import tempfile

import mock
from mock import Mock, patch, call
from pulp.common.compat import unittest
from pulp.devel.unit import util
from pulp.devel.unit.util import compare_dict
from pulp.plugins.conduits.repo_config import RepoConfigConduit
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository

from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM
from pulp_rpm.plugins.distributors.yum import distributor
from pulp_rpm.plugins.distributors.yum.distributor import YumHTTPDistributor


DISTRIBUTOR = 'pulp_rpm.plugins.distributors.yum.distributor'
CONFIGURATION = DISTRIBUTOR + '.configuration'


class YumDistributorTests(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp()

        self.distributor = distributor.YumHTTPDistributor()

    def tearDown(self):
        shutil.rmtree(self.working_dir)
        self.distributor = None

    def test_metadata(self):
        metadata = distributor.YumHTTPDistributor.metadata()

        for key in ('id', 'display_name', 'types'):
            self.assertTrue(key in metadata)

        self.assertEqual(metadata['id'], TYPE_ID_DISTRIBUTOR_YUM)
        self.assertEqual(metadata['display_name'], distributor.DISTRIBUTOR_DISPLAY_NAME)

    @patch('pulp_rpm.plugins.distributors.yum.distributor.platform_models')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.validate_config')
    def test_validate_config(self, mock_validate_config, m_platform_models):
        repo = Repository('test')
        m_repo = Mock(repo_id='test')
        m_platform_models.Repository.objects.get.return_value = m_repo
        config = PluginCallConfiguration(None, None)
        conduit = RepoConfigConduit(TYPE_ID_DISTRIBUTOR_YUM)

        self.distributor.validate_config(repo, config, conduit)

        mock_validate_config.assert_called_once_with(m_repo, config, conduit)

    @patch('pulp_rpm.plugins.distributors.yum.distributor.platform_models')
    @mock.patch('pulp_rpm.plugins.distributors.yum.distributor.publish')
    def test_publish_repo(self, mock_publish, m_platform_models):
        repo = Repository('test')
        m_platform_models.Repository.objects.get.return_value = Mock(repo_id='test')
        config = PluginCallConfiguration(None, None)
        conduit = RepoPublishConduit(repo.id, TYPE_ID_DISTRIBUTOR_YUM)

        self.distributor.publish_repo(repo, conduit, config)

        mock_publish.Publisher.return_value.publish.assert_called_once()

    def test_cancel_publish_repo(self):
        self.distributor._publisher = mock.MagicMock()

        self.distributor.cancel_publish_repo()

        self.assertTrue(self.distributor.canceled)
        self.distributor._publisher.cancel.assert_called_once()

        self.distributor._publisher = None

    @patch('pulp_rpm.plugins.distributors.yum.distributor.pulp_server_config')
    @patch('pulp_rpm.plugins.distributors.yum.distributor.platform_models')
    def test_create_consumer_payload(self, m_platform_models, m_config):
        local_distributor = YumHTTPDistributor()
        repo = Mock()
        repo.display_name = 'foo'
        repo.id = 'bar'
        m_repo = Mock(repo_id='bar', display_name='foo')
        m_platform_models.Repository.objects.get.return_value = m_repo
        config = {'https_ca': 'pear',
                  'gpgkey': 'kiwi',
                  'auth_cert': 'durian',
                  'auth_ca': True,
                  'http': True,
                  'https': True}
        binding_config = {}
        cert_file = os.path.join(self.working_dir, "orange_file")

        m_config.config = ConfigParser.SafeConfigParser()
        m_config.config.add_section('server')
        m_config.config.set('server', 'server_name', 'apple')
        m_config.config.add_section('security')
        m_config.config.set('security', 'ssl_ca_certificate', cert_file)
        with open(cert_file, 'w') as filewriter:
            filewriter.write("orange")

        result = local_distributor.create_consumer_payload(repo, config, binding_config)

        target = {
            'server_name': 'apple',
            'ca_cert': 'orange',
            'relative_path': '/pulp/repos/bar',
            'gpg_keys': {'pulp.key': 'kiwi'},
            'client_cert': 'durian',
            'protocols': ['http', 'https'],
            'repo_name': 'foo'
        }
        self.assertDictEqual(result, target)

    @patch('pulp_rpm.plugins.distributors.yum.distributor.pulp_server_config')
    @patch('pulp_rpm.plugins.distributors.yum.distributor.platform_models')
    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.load_config')
    def test_create_consumer_payload_global_auth(self, mock_load_config, m_platform_models,
                                                 m_config):
        test_distributor = YumHTTPDistributor()
        repo = Mock()
        repo.display_name = 'foo'
        repo.id = 'bar'
        m_repo = Mock(repo_id='bar', display_name='foo')
        m_platform_models.Repository.objects.get.return_value = m_repo
        config = {'https_ca': 'pear',
                  'gpgkey': 'kiwi',
                  'http': True,
                  'https': True}
        m_config.config = ConfigParser.SafeConfigParser()
        m_config.config.add_section('server')
        m_config.config.set('server', 'server_name', 'apple')
        m_config.config.add_section('security')
        m_config.config.set('security', 'ssl_ca_certificate', 'orange')

        binding_config = {}

        repo_auth_config = ConfigParser.SafeConfigParser()
        repo_auth_config.add_section('repos')
        repo_auth_config.set('repos', 'global_cert_location', self.working_dir)
        mock_load_config.return_value = repo_auth_config

        with open(os.path.join(self.working_dir, 'pulp-global-repo.cert'), 'w+') as cert_file:
            cert_file.write('cert')
        with open(os.path.join(self.working_dir, 'pulp-global-repo.key'), 'w+') as cert_file:
            cert_file.write('key')
        with open(os.path.join(self.working_dir, 'pulp-global-repo.ca'), 'w+') as cert_file:
            cert_file.write('ca')

        result = test_distributor.create_consumer_payload(repo, config, binding_config)

        target = {
            'server_name': 'apple',
            'ca_cert': 'pear',
            'relative_path': '/pulp/repos/bar',
            'gpg_keys': {'pulp.key': 'kiwi'},
            'protocols': ['http', 'https'],
            'repo_name': 'foo',
            'client_cert': None,
            'global_auth_cert': 'cert',
            'global_auth_key': 'key',
            'global_auth_ca': 'ca'
        }
        compare_dict(result, target)


@patch('pulp_rpm.plugins.distributors.yum.distributor.platform_models')
@patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_repo_relative_path')
@patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_master_publish_dir')
@patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_http_publish_dir')
@patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_https_publish_dir')
@patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.remove_cert_based_auth')
@patch('pulp_rpm.plugins.distributors.yum.distributor.shutil.rmtree')
@patch('pulp_rpm.plugins.distributors.yum.distributor.os')
@patch('pulp_rpm.plugins.distributors.yum.distributor.YumHTTPDistributor.'
       'clean_simple_hosting_directories')
class TestDistributorDistributorRemoved(unittest.TestCase):

    def setUp(self):
        # self._apply_mock_patches()
        self.working_dir = tempfile.mkdtemp()
        self.distributor = distributor.YumHTTPDistributor()
        self.mock_transfer_repo = Mock(id='foo')
        self.mock_repo = Mock(repo_id='foo')
        self.config = {}

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_distributor_remove_distributor_calls_get_master_publish_dir(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):

        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        m_get_master_publish_dir.assert_called_once_with(self.mock_repo, TYPE_ID_DISTRIBUTOR_YUM)

    def test_distributor_remove_distributor_calls_get_http_publish_dir(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        m_get_http_publish_dir.assert_called_once_with(self.config)

    def test_distributor_remove_distributor_calls_get_https_publish_dir(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        m_get_https_publish_dir.assert_called_once_with(self.config)

    def test_distributor_remove_distributor_calls_get_repo_relative_path_twice(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        rel_path_calls = [
            call(self.mock_repo, self.config),
            call(self.mock_repo, self.config),
        ]
        m_get_repo_relative_path.assert_has_calls(rel_path_calls)

    def test_distributor_remove_distributor_calls_remove_cert_based_auth(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        m_remove_cert_based_auth.assert_called_once_with(self.mock_repo, self.config)

    def test_distributor_remove_distributor_calls_clean_simple_hosting_directories(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        self.assertEqual(m_csh.call_count, 2)

    def test_distributor_remove_distributor_uses_rmtree_to_remove_working_dir_and_master_dir(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        rmtree_calls = [
            call(m_get_master_publish_dir.return_value, ignore_errors=True)
        ]
        m_rmtree.assert_has_calls(rmtree_calls)

    def test_distributor_remove_distributor_uses_unlink_to_remove_http_and_https_symlinks(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        unlink_calls = [
            call(m_os.path.join.return_value.rstrip.return_value),
            call(m_os.path.join.return_value.rstrip.return_value)
        ]
        m_os.unlink.assert_has_calls(unlink_calls)

    def test_distributor_remove_distributor_unlink_call_handles_OSError_raised(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        os_error_to_raise = OSError()
        os_error_to_raise.errno = errno.ENOENT
        m_os.unlink.side_effect = os_error_to_raise
        try:
            self.distributor.distributor_removed(self.mock_transfer_repo, self.config)
        except Exception:
            self.fail('Distributor unlink should handle symlinks that do not exist.')

    def test_distributor_remove_distributor_unlink_call_handles_non_oserror_raised(
            self, m_csh, m_os, m_rmtree, m_remove_cert_based_auth, m_get_https_publish_dir,
            m_get_http_publish_dir, m_get_master_publish_dir, m_get_repo_relative_path,
            m_platform_models):
        m_platform_models.Repository.objects.get.return_value = self.mock_repo
        os_error_to_raise = OSError()
        m_os.unlink.side_effect = os_error_to_raise
        self.assertRaises(OSError, self.distributor.distributor_removed, self.mock_transfer_repo,
                          self.config)


class TestCleanSimpleHostingDirectories(unittest.TestCase):
    """Test the clean_simple_hosting_directories method."""

    def setUp(self):
        """Setup a publish base"""
        self.working_dir = tempfile.mkdtemp()
        self.publish_base = os.path.join(self.working_dir, 'publish', 'dir')
        util.touch(os.path.join(self.publish_base, 'listing'))
        self.distributor = distributor.YumHTTPDistributor()

    def tearDown(self):
        """Cleanup the publish base"""
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def test_clean_ophaned_leaf(self):
        """
        Test that an orphaned leaf is removed.
        """
        listing_file_a = os.path.join(self.publish_base, 'a', 'listing')
        listing_file_b = os.path.join(self.publish_base, 'a', 'b', 'listing')
        listing_file_c = os.path.join(self.publish_base, 'a', 'b', 'c', 'listing')
        util.touch(listing_file_a)
        util.touch(listing_file_b)
        util.touch(listing_file_c)
        old_symlink = os.path.join(self.publish_base, 'a', 'b', 'c', 'path_to_removed_symlink')
        self.distributor.clean_simple_hosting_directories(old_symlink, self.publish_base)
        self.assertFalse(os.path.isdir(os.path.join(self.publish_base, 'a')))

    def test_clean_only_ophaned_leaf(self):
        """
        Test partially shared path, only unshared portion of ophan path should be removed.
        """
        listing_file_a = os.path.join(self.publish_base, 'a', 'listing')
        listing_file_b = os.path.join(self.publish_base, 'a', 'b', 'listing')
        listing_file_c = os.path.join(self.publish_base, 'a', 'b', 'c', 'listing')
        non_orphan_listing = os.path.join(self.publish_base, 'a', 'other', 'listing')
        non_orphan_file = os.path.join(self.publish_base, 'a', 'other', 'otherfile')
        util.touch(listing_file_a)
        util.touch(listing_file_b)
        util.touch(listing_file_c)
        util.touch(non_orphan_listing)
        util.touch(non_orphan_file)
        old_symlink = os.path.join(self.publish_base, 'a', 'b', 'c', 'path_to_removed_symlink')
        self.distributor.clean_simple_hosting_directories(old_symlink, self.publish_base)
        self.assertTrue(os.path.isdir(os.path.join(self.publish_base, 'a')))
        self.assertFalse(os.path.isdir(os.path.join(self.publish_base, 'a', 'b')))

    @mock.patch('pulp_rpm.plugins.distributors.yum.distributor.util')
    @mock.patch('pulp_rpm.plugins.distributors.yum.distributor.os.rmdir')
    def test_clean_with_concurrent_file_creation(self, mock_rmdir, mock_util):
        """
        Clean directories when a dir cannot be removed during orphaned directory removal.
        """
        mock_rmdir.side_effect = OSError()
        listing_file_a = os.path.join(self.publish_base, 'a', 'listing')
        updir = os.path.join(self.publish_base, 'a')
        util.touch(listing_file_a)
        old_symlink = os.path.join(self.publish_base, 'a', 'path_to_removed_symlink')
        self.distributor.clean_simple_hosting_directories(old_symlink, self.publish_base)
        mock_util.generate_listing_files.assert_called_once_with(updir, updir)


class TestEntryPoint(unittest.TestCase):
    """
    Test the entry_point method. This is really just to get good coverage numbers, but hey.
    """

    @patch('pulp_rpm.plugins.distributors.yum.distributor.read_json_config')
    def test_entry_point(self, mock_read_json):
        yum_distributor, config = distributor.entry_point()
        self.assertEqual(yum_distributor, distributor.YumHTTPDistributor)
        self.assertEqual(config, mock_read_json.return_value)
