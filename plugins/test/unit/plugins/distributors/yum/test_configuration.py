import os
import shutil
import tempfile
import unittest
from ConfigParser import SafeConfigParser

import mock
from mock import MagicMock, patch, ANY
from pulp.plugins.conduits.repo_config import RepoConfigConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository
from pulp.server.exceptions import MissingResource

from pulp_rpm.common.constants import CONFIG_KEY_CHECKSUM_TYPE, \
    SCRATCHPAD_DEFAULT_METADATA_CHECKSUM, CONFIG_DEFAULT_CHECKSUM
from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM
from pulp_rpm.common import constants
from pulp_rpm.plugins.distributors.yum import configuration


DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../../data/')


class YumDistributorConfigurationTests(unittest.TestCase):

    def setUp(self):
        super(YumDistributorConfigurationTests, self).setUp()

    def tearDown(self):
        super(YumDistributorConfigurationTests, self).tearDown()

    @staticmethod
    def _generate_call_config(**kwargs):
        config = PluginCallConfiguration(None, None)
        config.default_config.update(kwargs)
        return config

    # -- generalized validation tests ------------------------------------------

    def test_usable_directory(self):
        error_messages = []
        directory = tempfile.mkdtemp(prefix='test_yum_distributor-')

        try:
            configuration._validate_usable_directory('directory', directory, error_messages)

            self.assertEqual(len(error_messages), 0)

        finally:
            shutil.rmtree(directory)

    def test_usable_directory_bad_permissions(self):
        error_messages = []
        directory = tempfile.mkdtemp(prefix='test_yum_distributor-')
        os.chmod(directory, 0000)

        try:
            configuration._validate_usable_directory('directory', directory, error_messages)

            self.assertEqual(len(error_messages), 1)

        finally:
            os.chmod(directory, 0777)
            shutil.rmtree(directory)

    def test_usable_directory_missing(self):
        error_messages = []

        configuration._validate_usable_directory('directory', '/no/exits/', error_messages)

        self.assertEqual(len(error_messages), 1)

    def test_certificate(self):

        test_ca_path = os.path.join(DATA_DIR, 'test_ca.crt')
        with open(test_ca_path, 'r') as test_ca_handle:

            error_messages = []
            ca_cert = test_ca_handle.read()

            configuration._validate_certificate('cert', ca_cert, error_messages)

            self.assertEqual(len(error_messages), 0)

    def test_certificate_invalid(self):
        error_messages = []
        cert = 'nope'

        configuration._validate_certificate('cert', cert, error_messages)

        self.assertEqual(len(error_messages), 1)

    def test_dictionary(self):
        error_messages = []
        d = {}

        configuration._validate_dictionary('dict', d, error_messages)

        self.assertEqual(len(error_messages), 0)

    def test_dictionary_none_ok(self):
        error_messages = []
        d = None

        configuration._validate_dictionary('dict', d, error_messages, none_ok=True)

        self.assertEqual(len(error_messages), 0)

    def test_dictionary_none_not_ok(self):
        error_messages = []
        d = None

        configuration._validate_dictionary('dict', d, error_messages, none_ok=False)

        self.assertEqual(len(error_messages), 1)

    def test_dictionary_not_dict(self):
        error_messages = []
        d = ()

        configuration._validate_dictionary('dict', d, error_messages)

        self.assertEqual(len(error_messages), 1)

    def test_boolean(self):
        error_messages = []
        b = True

        configuration._validate_boolean('bool', b, error_messages)

        self.assertEqual(len(error_messages), 0)

    def test_boolean_none_ok(self):
        error_messages = []
        b = None

        configuration._validate_boolean('bool', b, error_messages, none_ok=True)

        self.assertEqual(len(error_messages), 0)

    def test_boolean_none_not_ok(self):
        error_messages = []
        b = None

        configuration._validate_boolean('bool', b, error_messages, none_ok=False)

        self.assertEqual(len(error_messages), 1)

    def test_boolean_not_bool(self):
        error_messages = []
        b = 0

        configuration._validate_boolean('bool', b, error_messages)

        self.assertEqual(len(error_messages), 1)

    # -- required option validation --------------------------------------------

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_boolean')
    def test_http(self, mock_validate_boolean):
        error_messages = []

        configuration._validate_http(False, error_messages)

        mock_validate_boolean.assert_called_once_with('http', False, error_messages)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_boolean')
    def test_https(self, mock_validate_boolean):
        error_messages = []

        configuration._validate_https(True, error_messages)

        mock_validate_boolean.assert_called_once_with('https', True, error_messages)

    def test_relative_url(self):
        error_messages = []
        url = 'foo/bar/baz/6.4/x86_64/os'

        configuration._validate_relative_url(url, error_messages)

        self.assertEqual(len(error_messages), 0)

    def test_relative_url_none(self):
        error_messages = []
        url = None

        configuration._validate_relative_url(url, error_messages)

        self.assertEqual(len(error_messages), 0)

    def test_relative_url_not_string(self):
        error_messages = []
        url = 42

        configuration._validate_relative_url(url, error_messages)

        self.assertEqual(len(error_messages), 1)

    # -- optional option validation --------------------------------------------

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_certificate')
    def test_auth_ca(self, mock_validate_certificate):
        error_messages = []
        auth_ca = 'Look ma, I\'m a CA'

        configuration._validate_auth_ca(auth_ca, error_messages)

        mock_validate_certificate.assert_called_once_with('auth_ca', auth_ca, error_messages)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_certificate')
    def test_auth_cert(self, mock_validate_certificate):
        error_messages = []
        auth_cert = 'Look ma, I\'m a cert'

        configuration._validate_auth_cert(auth_cert, error_messages)

        mock_validate_certificate.assert_called_once_with('auth_cert', auth_cert, error_messages)

    def test_checksum_types(self):

        for checksum_type in ('sha256', 'sha', 'sha1', 'md5', 'sha512'):
            error_messages = []

            configuration._validate_checksum_type(checksum_type, error_messages)

            self.assertEqual(len(error_messages), 0)

    def test_checksum_type_invalid(self):
        error_messages = []
        checksum_type = 'neverheardofit'

        configuration._validate_checksum_type(checksum_type, error_messages)

        self.assertEqual(len(error_messages), 1)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_usable_directory')
    def test_http_publish_dir(self, mock_validate_usable_directory):
        error_messages = []
        http_publish_dir = '/foo/bar/baz/'

        configuration._validate_http_publish_dir(http_publish_dir, error_messages)

        mock_validate_usable_directory.assert_called_once_with('http_publish_dir',
                                                               http_publish_dir, error_messages)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_usable_directory')
    def test_https_publish_dir(self, mock_validate_usable_directory):
        error_messages = []
        https_publish_dir = '/foo/bar/baz/'

        configuration._validate_https_publish_dir(https_publish_dir, error_messages)

        mock_validate_usable_directory.assert_called_once_with('https_publish_dir',
                                                               https_publish_dir, error_messages)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_boolean')
    def test_protected(self, mock_validate_boolean):
        error_messages = []

        configuration._validate_protected(True, error_messages)

        mock_validate_boolean.assert_called_once_with('protected', True, error_messages, False)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_list')
    def test_skip(self, mock_validate_list):
        error_messages = []
        skip = {}

        configuration._validate_skip(skip, error_messages)

        mock_validate_list.assert_called_once_with('skip', skip, error_messages, False)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_boolean')
    def test_skip_pkg_tags(self, mock_validate_boolean):
        error_messages = []

        configuration._validate_skip_pkg_tags(True, error_messages)

        mock_validate_boolean.assert_called_once_with('skip_pkg_tags', True, error_messages)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_boolean')
    def test_generate_sqlite(self, mock_validate_boolean):
        error_messages = []

        configuration._validate_generate_sqlite(False, error_messages)

        mock_validate_boolean.assert_called_once_with('generate_sqlite', False, error_messages,
                                                      False)

    # prevent this from running, because it has unexpected side-effects
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.process_cert_based_auth')
    def test_gpg_key(self, mock_process_auth):
        config_dict = {
            'http': True,
            'https': True,
            'relative_url': 'a/b/c',
            'gpgkey': '/tmp/my.gpg',
        }
        config = self._generate_call_config(**config_dict)

        valid, reason = configuration.validate_config(Repository('myrepo'),
                                                      config, mock.MagicMock())

        self.assertTrue(valid is True)
        self.assertTrue(reason is None)

    # -- public api ------------------------------------------------------------

    def test_get_http_publish_dir_default(self):

        config = self._generate_call_config()

        http_publish_dir = configuration.get_http_publish_dir(config)

        self.assertEqual(http_publish_dir, configuration.HTTP_PUBLISH_DIR)

    def test_get_http_publish_dir_configured(self):

        configured_http_publish_dir = '/not/default/publish/dir/'
        config = self._generate_call_config(http_publish_dir=configured_http_publish_dir)

        http_publish_dir = configuration.get_http_publish_dir(config)

        self.assertEqual(http_publish_dir, configured_http_publish_dir)

    def test_get_https_publish_dir_default(self):

        config = self._generate_call_config()

        https_publish_dir = configuration.get_https_publish_dir(config)

        self.assertEqual(https_publish_dir, configuration.HTTPS_PUBLISH_DIR)

    def test_get_https_publish_dir_configured(self):

        configured_https_publish_dir = '/not/default/publish/dir/'
        config = self._generate_call_config(https_publish_dir=configured_https_publish_dir)

        https_publish_dir = configuration.get_https_publish_dir(config)

        self.assertEqual(https_publish_dir, configured_https_publish_dir)

    def test_get_repo_relative_path_repo_id(self):
        repo_id = 'Highlander'
        repo = Repository(repo_id)
        config = self._generate_call_config()

        relative_dir = configuration.get_repo_relative_path(repo, config)

        self.assertEqual(relative_dir, repo_id)

    def test_get_repo_relative_path_configured(self):
        repo_id = 'Spaniard'
        repo = Repository(repo_id)
        configured_relative_url = '/there/can/be/only/one/'
        config = self._generate_call_config(relative_url=configured_relative_url)

        relative_url = configuration.get_repo_relative_path(repo, config)

        # get_relative_path should strip off the leading '/'
        self.assertEqual(relative_url, configured_relative_url[1:])

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_http')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_https')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_relative_url')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_auth_ca')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_auth_cert')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_checksum_type')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_http_publish_dir')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_https_publish_dir')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_protected')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_skip')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_skip_pkg_tags')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._validate_generate_sqlite')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.'
                '_check_for_relative_path_conflicts')
    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.process_cert_based_auth')
    def test_validate_config(self, *mock_methods):
        config_kwargs = {'http': True,
                         'https': True,
                         'relative_url': None,
                         'auth_ca': 'CA',
                         'auth_cert': 'CERT',
                         'checksum_type': 'sha256',
                         'http_publish_dir': '/http/path/',
                         'https_publish_dir': 'https/path/',
                         'protected': True,
                         'skip': {'drpms': 1},
                         'skip_pkg_tags': True,
                         'generate_sqlite': False}

        repo = Repository('test')
        config = self._generate_call_config(**config_kwargs)
        conduit = RepoConfigConduit(TYPE_ID_DISTRIBUTOR_YUM)

        valid, reasons = configuration.validate_config(repo, config, conduit)

        for mock_method in mock_methods:
            self.assertEqual(mock_method.call_count, 1)

        self.assertTrue(valid)
        self.assertEqual(reasons, None)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.'
                '_check_for_relative_path_conflicts')
    def test_validate_config_missing_required(self, mock_check):
        repo = Repository('test')
        config = self._generate_call_config(http=True, https=False)
        conduit = RepoConfigConduit(TYPE_ID_DISTRIBUTOR_YUM)

        valid, reasons = configuration.validate_config(repo, config, conduit)

        self.assertFalse(valid)

        expected_reason = 'Configuration key [relative_url] is required, but was not provided'
        self.assertEqual(reasons, expected_reason)

        mock_check.assert_called_once_with(repo, config.flatten(), conduit, [expected_reason])

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.'
                '_check_for_relative_path_conflicts')
    def test_validate_config_unsupported_keys(self, mock_check):
        repo = Repository('test')
        config = self._generate_call_config(http=True, https=False, relative_url=None, foo='bar')
        conduit = RepoConfigConduit(TYPE_ID_DISTRIBUTOR_YUM)

        valid, reasons = configuration.validate_config(repo, config, conduit)

        self.assertFalse(valid)

        expected_reason = 'Configuration key [foo] is not supported'
        self.assertEqual(reasons, expected_reason)

        self.assertEqual(mock_check.call_count, 1)

    def test_load_config(self):
        config_handle, config_path = tempfile.mkstemp(prefix='test_yum_distributor-')
        os.close(config_handle)

        try:
            config = configuration.load_config(config_path)

            self.assertTrue(isinstance(config, SafeConfigParser))

        finally:
            os.unlink(config_path)

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration._LOG')
    def test_load_config_fails(self, mock_log):
        #Test to ensure that we log a warning if the config can't be loaded
        configuration.load_config("/bad/config/path")
        self.assertTrue(mock_log.warning.called)

    # -- conflicting relative paths --------------------------------------------

    def test_relative_path_conflicts_none(self):
        repo = Repository('test')
        config = {}
        conduit = mock.MagicMock()
        conduit.get_repo_distributors_by_relative_url = mock.MagicMock(return_value=[])
        error_messages = []

        configuration._check_for_relative_path_conflicts(repo, config, conduit, error_messages)

        self.assertEqual(conduit.get_repo_distributors_by_relative_url.call_count, 1)
        self.assertEqual(len(error_messages), 0)

    def test_relative_path_conflicts_conflicts(self):
        repo = Repository('test')
        config = {}
        conflicting_distributor = {'repo_id': 'i_suck',
                                   'config': {'relative_url': 'test'}}
        conduit = mock.MagicMock()
        conduit.get_repo_distributors_by_relative_url = mock.MagicMock(
            return_value=[conflicting_distributor])
        error_messages = []

        configuration._check_for_relative_path_conflicts(repo, config, conduit, error_messages)

        self.assertEqual(len(error_messages), 1)

    # -- cert based auth tests -------------------------------------------------

    @mock.patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.add_protected_repo')
    @mock.patch('pulp_rpm.repo_auth.repo_cert_utils.RepoCertUtils.write_consumer_cert_bundle')
    def test_cert_based_auth_ca_and_cert(self, mock_write_consumer_cert_bundle,
                                         mock_add_protected_repo):
        repo = Repository('test')
        config = {'auth_ca': 'looks legit',
                  'auth_cert': '1234567890'}
        bundle = {'ca': config['auth_ca'], 'cert': config['auth_cert']}

        configuration.process_cert_based_auth(repo, config)

        mock_write_consumer_cert_bundle.assert_called_once_with(repo.id, bundle)
        mock_add_protected_repo.assert_called_once_with(repo.id, repo.id)

    @mock.patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_cert_based_auth_ca_no_cert(self, mock_delete_protected_repo):
        repo = Repository('test')
        config = {'auth_ca': 'looks not so legit'}

        configuration.process_cert_based_auth(repo, config)

        mock_delete_protected_repo.assert_called_once_with(repo.id)

    @mock.patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_cert_based_auth_no_ca_no_cert(self, mock_delete_protected_repo):
        repo = Repository('test')

        configuration.process_cert_based_auth(repo, {})

        mock_delete_protected_repo.assert_called_once_with(repo.id)

    @mock.patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_remove_cert_based_auth(self, mock_delete_protected_repo):
        repo = Repository('test')
        config = {}

        configuration.remove_cert_based_auth(repo, config)

        mock_delete_protected_repo.assert_called_once_with(repo.id)


class TestGetExportRepoPublishDirs(unittest.TestCase):

    def test_both_dirs(self):
        config = PluginCallConfiguration({}, {constants.PUBLISH_HTTP_KEYWORD: True,
                                              constants.PUBLISH_HTTPS_KEYWORD: True})
        repo = mock.Mock(id='foo')
        dirs = configuration.get_export_repo_publish_dirs(repo, config)
        self.assertEquals(dirs, [
            os.path.join(configuration.HTTP_EXPORT_DIR, 'foo'),
            os.path.join(configuration.HTTPS_EXPORT_DIR, 'foo')])

    def test_no_dirs(self):
        config = PluginCallConfiguration({}, {})
        repo = mock.Mock(id='foo')
        dirs = configuration.get_export_repo_publish_dirs(repo, config)
        self.assertEquals(dirs, [])


class TestGetExportRepoGroupPublishDirs(unittest.TestCase):

    def test_both_dirs(self):
        config = PluginCallConfiguration({}, {constants.PUBLISH_HTTP_KEYWORD: True,
                                              constants.PUBLISH_HTTPS_KEYWORD: True})
        repo = mock.Mock(id='foo')
        dirs = configuration.get_export_repo_group_publish_dirs(repo, config)
        self.assertEquals(dirs, [
            os.path.join(configuration.HTTP_EXPORT_GROUP_DIR, 'foo'),
            os.path.join(configuration.HTTPS_EXPORT_GROUP_DIR, 'foo')])

    def test_no_dirs(self):
        config = PluginCallConfiguration({}, {})
        repo = mock.Mock(id='foo')
        dirs = configuration.get_export_repo_group_publish_dirs(repo, config)
        self.assertEquals(dirs, [])


class TestConfigurationValidationHelpers(unittest.TestCase):

    def test_validate_list_success(self):
        error_messages = []
        configuration._validate_list('foo', ['bar'], error_messages)
        self.assertEquals(0, len(error_messages))

    def test_validate_list_error(self):
        error_messages = []
        configuration._validate_list('foo', 'bar', error_messages)
        self.assertEquals(1, len(error_messages))

    def test_validate_list_none_ok(self):
        error_messages = []
        configuration._validate_list('foo', None, error_messages, none_ok=True)
        self.assertEquals(0, len(error_messages))

    def test_validate_list_none_ok_false(self):
        error_messages = []
        configuration._validate_list('foo', None, error_messages, none_ok=False)
        self.assertEquals(1, len(error_messages))


class TestGetRepoChecksumType(unittest.TestCase):

    def setUp(self):
        self.config = PluginCallConfiguration({}, {})
        self.mock_conduit = MagicMock()

    def test_get_repo_checksum_from_config(self):
        config_with_checksum = PluginCallConfiguration({}, {CONFIG_KEY_CHECKSUM_TYPE: 'sha1'})
        self.assertEquals('sha1', configuration.get_repo_checksum_type(self.mock_conduit,
                                                                       config_with_checksum))

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_from_scratchpad(self, mock_distributor_manager):
        self.mock_conduit.get_repo_scratchpad.return_value = \
            {SCRATCHPAD_DEFAULT_METADATA_CHECKSUM: 'sha1'}
        self.assertEquals('sha1',
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_not_in_scratchpad(self, mock_distributor_manager):
        #Test with other data in the scratchpad
        self.mock_conduit.get_repo_scratchpad.return_value = \
            {'foo': 'bar'}
        self.assertEquals(CONFIG_DEFAULT_CHECKSUM,
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_update_distributor_config(self, mock_distributor_manager):
        self.mock_conduit.get_repo_scratchpad.return_value = \
            {SCRATCHPAD_DEFAULT_METADATA_CHECKSUM: 'sha1'}

        mock_distributor_manager.return_value.get_distributor.return_value = \
            {'distributor_type_id': TYPE_ID_DISTRIBUTOR_YUM}

        self.assertEquals('sha1',
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))
        mock_distributor_manager.return_value.update_distributor_config.\
            assert_called_with(ANY, ANY, {'checksum_type': 'sha1'})

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_update_distributor_config_non_yum(self, mock_distributor_manager):
        """
        If this isn't a yum distributor the config should not be updated in the database
        """
        self.mock_conduit.get_repo_scratchpad.return_value = \
            {SCRATCHPAD_DEFAULT_METADATA_CHECKSUM: 'sha1'}
        self.assertEquals('sha1',
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))
        self.assertFalse(mock_distributor_manager.return_value.update_distributor_config.called)

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_from_default(self, mock_distributor_manager):
        self.mock_conduit.get_repo_scratchpad.return_value = {'foo': 'value'}
        self.assertEquals(CONFIG_DEFAULT_CHECKSUM,
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))

    def test_get_repo_checksum_convert_sha_to_sha1(self):
        config_with_checksum = PluginCallConfiguration({}, {CONFIG_KEY_CHECKSUM_TYPE: 'sha'})
        self.assertEquals('sha1', configuration.get_repo_checksum_type(self.mock_conduit,
                                                                       config_with_checksum))

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_conduit_with_no_scratchpad(self, mock_distributor_manager):
        self.mock_conduit.get_repo_scratchpad.return_value = None
        self.assertEquals(CONFIG_DEFAULT_CHECKSUM,
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_get_repo_checksum_distributor_id_not_yum_plugin(self, mock_distributor_manager):
        self.mock_conduit.get_repo_scratchpad.return_value = None
        mock_distributor_manager.return_value.get_distributor.side_effect = MissingResource()
        self.assertEquals(CONFIG_DEFAULT_CHECKSUM,
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))
