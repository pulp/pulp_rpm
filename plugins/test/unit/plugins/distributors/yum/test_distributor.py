# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import tempfile
import unittest
import shutil
import os
import ConfigParser

import mock
from mock import Mock, patch

from pulp.devel.unit.util import compare_dict
from pulp.plugins.conduits.repo_config import RepoConfigConduit
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository
from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM
from pulp_rpm.plugins.distributors.yum import distributor
from pulp_rpm.plugins.distributors.yum.distributor import YumHTTPDistributor, pulp_server_config


class YumDistributorTests(unittest.TestCase):

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()

        self.distributor = distributor.YumHTTPDistributor()

    def tearDown(self):
        shutil.rmtree(self.working_dir)
        self.distributor = None

    # -- metadata test ---------------------------------------------------------

    def test_metadata(self):

        metadata = distributor.YumHTTPDistributor.metadata()

        for key in ('id', 'display_name', 'types'):
            self.assertTrue(key in metadata)

        self.assertEqual(metadata['id'], TYPE_ID_DISTRIBUTOR_YUM)
        self.assertEqual(metadata['display_name'], distributor.DISTRIBUTOR_DISPLAY_NAME)

    # -- configuration test ----------------------------------------------------

    @mock.patch('pulp_rpm.plugins.distributors.yum.configuration.validate_config')
    def test_validate_config(self, mock_validate_config):
        repo = Repository('test')
        config = PluginCallConfiguration(None, None)
        conduit = RepoConfigConduit(TYPE_ID_DISTRIBUTOR_YUM)

        self.distributor.validate_config(repo, config, conduit)

        mock_validate_config.assert_called_once_with(repo, config, conduit)

    # -- publish tests ---------------------------------------------------------

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher.publish')
    def test_publish_repo(self, mock_publish):
        repo = Repository('test')
        config = PluginCallConfiguration(None, None)
        conduit = RepoPublishConduit(repo.id, TYPE_ID_DISTRIBUTOR_YUM)

        self.distributor.publish_repo(repo, conduit, config)

        mock_publish.assert_called_once()

    def test_cancel_publish_repo(self):

        self.distributor._publisher = mock.MagicMock()

        self.distributor.cancel_publish_repo()

        self.assertTrue(self.distributor.canceled)
        self.distributor._publisher.cancel.assert_called_once()

        self.distributor._publisher = None

    def test_create_consumer_payload(self):
        local_distributor = YumHTTPDistributor()
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
        cert_file = os.path.join(self.working_dir, "orange_file")
        with open(cert_file, 'w') as filewriter:
            filewriter.write("orange")

        pulp_server_config.set('security', 'ssl_ca_certificate', cert_file)

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
        compare_dict(result, target)

    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.load_config')
    def test_create_consumer_payload_global_auth(self, mock_load_config):
        test_distributor = YumHTTPDistributor()
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

    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.remove_cert_based_auth')
    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_master_publish_dir')
    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_http_publish_dir')
    @patch('pulp_rpm.plugins.distributors.yum.distributor.configuration.get_https_publish_dir')
    def test_distributor_removed(self, mock_http, mock_https, mock_master, remove_cert):
        mock_http.return_value = os.path.join(self.working_dir, 'http')
        mock_https.return_value = os.path.join(self.working_dir, 'https')
        mock_master.return_value = os.path.join(self.working_dir, 'master')
        os.makedirs(mock_http.return_value)
        os.makedirs(mock_https.return_value)
        os.makedirs(mock_master.return_value)
        os.makedirs(os.path.join(self.working_dir, 'working'))
        test_distributor = YumHTTPDistributor()
        repo = Mock()
        repo.id = 'bar'
        repo.working_dir = os.path.join(self.working_dir, 'working')
        config = {}
        test_distributor.distributor_removed(repo, config)

        self.assertEquals(0, len(os.listdir(self.working_dir)))

        remove_cert.assert_called_with(repo, config)


class TestEntryPoint(unittest.TestCase):
    """
    Test the entry_point method. This is really just to get good coverage numbers, but hey.
    """
    @patch('pulp_rpm.plugins.distributors.yum.distributor.read_json_config')
    def test_entry_point(self, mock_read_json):
        yum_distributor, config = distributor.entry_point()
        self.assertEqual(yum_distributor, distributor.YumHTTPDistributor)
        self.assertEqual(config, mock_read_json.return_value)
