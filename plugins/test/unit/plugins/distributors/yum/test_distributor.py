import unittest
import ConfigParser
import tempfile
import shutil
import os

from mock import Mock, patch
from pulp.devel.unit.util import compare_dict

from pulp_rpm.plugins.distributors.yum.distributor import YumHTTPDistributor, pulp_server_config


class TestDistributor(unittest.TestCase):

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_create_consumer_payload(self):
        distrubutor = YumHTTPDistributor()
        repo = Mock()
        repo.display_name = 'foo'
        repo.id = 'bar'
        config = {'https_ca': 'pear',
                  'gpgkey': 'kiwi',
                  'auth_cert': 'durian',
                  'auth_ca': True,
                  'http': True,
                  'https': True}
        binding_config = {}
        pulp_server_config.set('server', 'server_name', 'apple')
        pulp_server_config.set('security', 'ssl_ca_certificate', 'orange')

        result = distrubutor.create_consumer_payload(repo, config, binding_config)

        target = {
            'server_name': 'apple',
            'ca_cert': 'pear',
            'relative_path': '/pulp/repos/bar',
            'gpg_keys': {'pulp.key': 'kiwi'},
            'client_cert': 'durian',
            'protocols': ['http', 'https'],
            'repo_name': 'foo'
        }
        compare_dict(result, target)

    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.load_config')
    def test_create_consumer_payload_global_auth(self, mock_load_config):
        distrubutor = YumHTTPDistributor()
        repo = Mock()
        repo.display_name = 'foo'
        repo.id = 'bar'
        config = {'https_ca': 'pear',
                  'gpgkey': 'kiwi',
                  'http': True,
                  'https': True}
        binding_config = {}
        pulp_server_config.set('server', 'server_name', 'apple')
        pulp_server_config.set('security', 'ssl_ca_certificate', 'orange')

        repo_auth_config = ConfigParser.SafeConfigParser()
        repo_auth_config.add_section('repos')
        repo_auth_config.set('repos', 'global_cert_location', self.working_dir)
        mock_load_config.return_value = repo_auth_config

        with open(os.path.join(self.working_dir, 'pulp-global-repo.cert'), 'w+') as file:
            file.write('cert')
        with open(os.path.join(self.working_dir, 'pulp-global-repo.key'), 'w+') as file:
            file.write('key')
        with open(os.path.join(self.working_dir, 'pulp-global-repo.ca'), 'w+') as file:
            file.write('ca')

        result = distrubutor.create_consumer_payload(repo, config, binding_config)

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
