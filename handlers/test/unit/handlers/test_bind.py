import unittest

from pulp.agent.lib.conduit import Conduit
import mock

from pulp_rpm.handlers import bind


class TestRepoHandler(unittest.TestCase):
    """
    Tests for the RepoHandler object.
    """

    @mock.patch('pulp_rpm.handlers.bind.repolib.bind')
    def test_bind_passes_ca_path(self, repolib_bind):
        """
        Ensure that the bind() method properly passes the ca_path flag on to the repolib.bind()
        function.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = mock.MagicMock(autospec=Conduit)
        ca_path = '/path/to/ca.crt'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = mock.MagicMock()
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

    @mock.patch('pulp_rpm.handlers.bind.repolib.bind')
    def test_bind_passes_verify_ssl_false(self, repolib_bind):
        """
        Ensure that the bind() method properly passes the verify_ssl flag on to the repolib.bind()
        function when it is false.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = mock.MagicMock(autospec=Conduit)
        # Case shouldn't matter
        verify_ssl = 'fAlSe'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = mock.MagicMock()
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

    @mock.patch('pulp_rpm.handlers.bind.repolib.bind')
    def test_bind_passes_verify_ssl_non_bool(self, repolib_bind):
        """
        Ensure that the bind() method properly interprets the verify_ssl flag when it is a typo.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = mock.MagicMock(autospec=Conduit)
        verify_ssl = 'some_typo'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = mock.MagicMock()
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

    @mock.patch('pulp_rpm.handlers.bind.repolib.bind')
    def test_bind_passes_verify_ssl_true(self, repolib_bind):
        """
        Ensure that the bind() method properly passes the verify_ssl flag on to the repolib.bind()
        function when it is true.
        """
        cfg = {}
        handler = bind.RepoHandler(cfg)
        conduit = mock.MagicMock(autospec=Conduit)
        # Case shouldn't matter
        verify_ssl = 'tRuE'

        def get_consumer_config():
            class Config(object):
                def graph(self):
                    config = mock.MagicMock()
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
