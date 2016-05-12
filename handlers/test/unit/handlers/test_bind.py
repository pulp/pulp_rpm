import os

from unittest import TestCase

from mock import patch, MagicMock

from pulp.common.config import Config
from pulp.agent.lib.conduit import Conduit

from pulp_rpm.handlers import bind


PACKAGE = 'pulp_rpm.handlers'

MODULE = '.'.join((PACKAGE, 'bind'))


class TestRepoHandler(TestCase):
    """
    Tests for the RepoHandler object.
    """

    @patch(MODULE + '.BindReport')
    @patch(MODULE + '.RepoHandler._urls')
    @patch(PACKAGE + '.lib.repolib.bind')
    def test_bind(self, repolib_bind, urls, bind_report):
        options = {}
        conduit = MagicMock(autospec=Conduit)
        repo_id = 'animals'
        repo_name = 'Animals'
        cfg = {
            'server': {
                'verify_ssl': 'true'
            },
            'filesystem': {
                'repo_file': 'pulp.repo',
                'mirror_list_dir': '/tmp/mirror-list',
                'gpg_keys_dir': '/tmp/gpg',
                'cert_dir': '/tmp/certs',
            }
        }
        cfg = Config(cfg)
        conduit.get_consumer_config.return_value = cfg
        details = {
            'repo_name': repo_name,
            'protocols': ['https'],
            'server_name': 'content-world',
            'relative_path': 'relative/path'
        }
        binding = {
            'type_id': 'dog',
            'repo_id': repo_id,
            'details': details
        }
        urls.return_value = ['https://content-world']

        # test
        handler = bind.RepoHandler({})
        report = handler.bind(conduit, binding, options)

        # validation
        cfg = cfg.graph()
        bind_report.assert_called_once_with(repo_id)
        repolib_bind.assert_called_once_with(
            cfg.filesystem.repo_file,
            os.path.join(cfg.filesystem.mirror_list_dir, repo_id),
            cfg.filesystem.gpg_keys_dir,
            cfg.filesystem.cert_dir,
            repo_id,
            repo_name,
            urls.return_value,
            details.get('gpg_keys', {}),
            details.get('client_cert'),
            len(urls.return_value) > 0,
            verify_ssl=True,
            ca_path=cfg.server.ca_path)
        bind_report.return_value.set_succeeded.assert_called_once_with()
        self.assertEqual(bind_report.return_value, report)

    @patch(MODULE + '.BindReport')
    @patch(PACKAGE + '.lib.repolib.unbind')
    def test_unbind(self, repolib_unbind, bind_report):
        options = {}
        conduit = MagicMock(autospec=Conduit)
        repo_id = 'animals'
        cfg = {
            'filesystem': {
                'repo_file': 'pulp.repo',
                'mirror_list_dir': '/tmp/mirror-list',
                'gpg_keys_dir': '/tmp/gpg',
                'cert_dir': '/tmp/certs',
            }
        }
        cfg = Config(cfg)
        conduit.get_consumer_config.return_value = cfg

        # test
        handler = bind.RepoHandler({})
        report = handler.unbind(conduit, repo_id, options)

        # validation
        cfg = cfg.graph()
        bind_report.assert_called_once_with(repo_id)
        repolib_unbind.assert_called_once_with(
            cfg.filesystem.repo_file,
            os.path.join(cfg.filesystem.mirror_list_dir, repo_id),
            cfg.filesystem.gpg_keys_dir,
            cfg.filesystem.cert_dir,
            repo_id)
        bind_report.return_value.set_succeeded.assert_called_once_with()
        self.assertEqual(bind_report.return_value, report)

    @patch(MODULE + '.CleanReport')
    @patch(PACKAGE + '.lib.repolib.delete_repo_file')
    def test_clean(self, delete, clean_report):
        conduit = MagicMock(autospec=Conduit)
        cfg = {
            'filesystem': {
                'repo_file': 'pulp.repo',
            }
        }
        cfg = Config(cfg)
        conduit.get_consumer_config.return_value = cfg

        # test
        handler = bind.RepoHandler({})
        report = handler.clean(conduit)

        # validation
        cfg = cfg.graph()
        clean_report.assert_called_once_with()
        delete.assert_called_once_with(cfg.filesystem.repo_file)
        clean_report.return_value.set_succeeded.assert_called_once_with()
        self.assertEqual(clean_report.return_value, report)

    @patch(MODULE + '.RepoHandler._protocol')
    def test_urls(self, protocol):
        protocol.return_value = 'https'
        details = {
            'server_name': 'content-world',
            'relative_path': '/relative/path',
        }

        # test
        handler = bind.RepoHandler({})
        urls = handler._urls(details)

        # validation
        self.assertEqual(urls, ['https://content-world/relative/path'])

    def test_protocol(self):
        details = {
            'protocols': ['http', 'https']
        }

        # test
        handler = bind.RepoHandler({})
        protocol = handler._protocol(details)

        # validation
        self.assertEqual(protocol, 'https')

    @patch(MODULE + '.RepoHandler._protocol')
    def test_urls_no_protocol(self, protocol):
        protocol.return_value = None

        # test
        handler = bind.RepoHandler({})
        urls = handler._urls({})

        # validation
        self.assertEqual(urls, [])

    @patch(PACKAGE + '.lib.repolib.bind')
    def test_bind_passes_ca_path(self, repolib_bind):
        """
        Ensure that the bind() method properly passes the ca_path flag on to the repolib.bind()
        function.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = MagicMock(autospec=Conduit)
        ca_path = '/path/to/ca.crt'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = MagicMock()
                    config.server.ca_path = ca_path
                    return config

            return Config()

        conduit.get_consumer_config = get_consumer_config
        options = 'unused'
        binding = {
            'type_id': 'some_type', 'repo_id': 'some_repo',
            'details': {'repo_name': 'repo_id', 'protocols': ['https'],
                        'server_name': 'some_host', 'relative_path': 'relative/path'}}

        handler.bind(conduit, binding, options)

        self.assertEqual(repolib_bind.call_count, 1)
        # Let's just focus on asserting that the ca_path was correct
        self.assertEqual(repolib_bind.mock_calls[0][2]['ca_path'], ca_path)

    @patch(PACKAGE + '.lib.repolib.bind')
    def test_bind_passes_verify_ssl_false(self, repolib_bind):
        """
        Ensure that the bind() method properly passes the verify_ssl flag on to the repolib.bind()
        function when it is false.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = MagicMock(autospec=Conduit)
        # Case shouldn't matter
        verify_ssl = 'fAlSe'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = MagicMock()
                    config.server.verify_ssl = verify_ssl
                    return config

            return Config()

        conduit.get_consumer_config = get_consumer_config
        options = 'unused'
        binding = {
            'type_id': 'some_type', 'repo_id': 'some_repo',
            'details': {'repo_name': 'repo_id', 'protocols': ['https'],
                        'server_name': 'some_host', 'relative_path': 'relative/path'}}

        handler.bind(conduit, binding, options)

        self.assertEqual(repolib_bind.call_count, 1)
        # Let's just focus on asserting that verify_ssl was correct, and that it was correctly
        # interpreted as a boolean
        self.assertEqual(repolib_bind.mock_calls[0][2]['verify_ssl'], False)

    @patch(PACKAGE + '.lib.repolib.bind')
    def test_bind_passes_verify_ssl_non_bool(self, repolib_bind):
        """
        Ensure that the bind() method properly interprets the verify_ssl flag when it is a typo.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = MagicMock(autospec=Conduit)
        verify_ssl = 'some_typo'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = MagicMock()
                    config.server.verify_ssl = verify_ssl
                    return config

            return Config()

        conduit.get_consumer_config = get_consumer_config
        options = 'unused'
        binding = {
            'type_id': 'some_type', 'repo_id': 'some_repo',
            'details': {'repo_name': 'repo_id', 'protocols': ['https'],
                        'server_name': 'some_host', 'relative_path': 'relative/path'}}

        handler.bind(conduit, binding, options)

        self.assertEqual(repolib_bind.call_count, 1)
        # Let's just focus on asserting that verify_ssl was correct, and that it was correctly
        # interpreted as a boolean. It should be true, since we should default to secure.
        self.assertEqual(repolib_bind.mock_calls[0][2]['verify_ssl'], True)

    @patch(PACKAGE + '.lib.repolib.bind')
    def test_bind_passes_verify_ssl_true(self, repolib_bind):
        """
        Ensure that the bind() method properly passes the verify_ssl flag on to the repolib.bind()
        function when it is true.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = MagicMock(autospec=Conduit)
        # Case shouldn't matter
        verify_ssl = 'tRuE'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = MagicMock()
                    config.server.verify_ssl = verify_ssl
                    return config
            return Config()

        conduit.get_consumer_config = get_consumer_config
        options = 'unused'
        binding = {
            'type_id': 'some_type', 'repo_id': 'some_repo',
            'details': {'repo_name': 'repo_id', 'protocols': ['https'],
                        'server_name': 'some_host', 'relative_path': 'relative/path'}}

        handler.bind(conduit, binding, options)

        self.assertEqual(repolib_bind.call_count, 1)
        # Let's just focus on asserting that verify_ssl was correct, and that it was correctly
        # interpreted as a boolean
        self.assertEqual(repolib_bind.mock_calls[0][2]['verify_ssl'], True)
