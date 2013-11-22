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

import unittest

from mock import MagicMock, patch, ANY

from pulp.plugins.config import PluginCallConfiguration

from pulp_rpm.common.constants import CONFIG_DEFAULT_CHECKSUM, \
    SCRATCHPAD_DEFAULT_METADATA_CHECKSUM, CONFIG_KEY_CHECKSUM_TYPE
from pulp_rpm.plugins.distributors.yum import configuration


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
    def test_get_repo_checksum_update_distributor_config(self, mock_distributor_manager):
        self.mock_conduit.get_repo_scratchpad.return_value = \
            {SCRATCHPAD_DEFAULT_METADATA_CHECKSUM: 'sha1'}
        self.assertEquals('sha1',
                          configuration.get_repo_checksum_type(self.mock_conduit, self.config))
        mock_distributor_manager.return_value.update_distributor_config.\
            assert_called_with(ANY, ANY, {'checksum_type': 'sha1'})

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