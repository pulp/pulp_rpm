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

import os
import sys
import unittest

import mock

from pulp.plugins.conduits.repo_config import RepoConfigConduit
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository

PACKAGE_PATH = os.path.join(os.path.dirname(__file__), '../../')
sys.path.insert(0, PACKAGE_PATH)

from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM
from pulp_rpm.plugins.distributors.yum import distributor


class YumDistributorTests(unittest.TestCase):

    def setUp(self):
        super(YumDistributorTests, self).setUp()

        self.distributor = distributor.YumHTTPDistributor()

    def tearDown(self):
        super(YumDistributorTests, self).tearDown()

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

        self.distributor.publish_repo(repo,conduit, config)

        mock_publish.assert_called_once()

    def test_cancel_publish_repo(self):

        self.distributor._publisher = mock.MagicMock()

        self.distributor.cancel_publish_repo(None, None)

        self.assertTrue(self.distributor.canceled)
        self.distributor._publisher.cancel.assert_called_once()

        self.distributor._publisher = None
