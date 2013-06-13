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
import shutil
import sys
import tempfile

import mock

from pulp.plugins.model import Repository
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp_rpm.common.ids import TYPE_ID_YUM_REPO_METADATA_FILE

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")

from yum_importer.importer import YumImporter

import data_dir
import http_static_test_server
import mock_conduits
import rpm_support_base


TEST_DRPM_REPO_FEED = 'http://localhost:8088/%s/test_drpm_repo/published/test_drpm_repo/' % \
    data_dir.relative_path_to_data_dir()


class CustomMetadataTests(rpm_support_base.PulpRPMTests):

    @classmethod
    def setUpClass(cls):
        super(CustomMetadataTests, cls).setUpClass()
        cls.server = http_static_test_server.HTTPStaticTestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        super(CustomMetadataTests, cls).tearDownClass()
        cls.server.stop()
        cls.server = None

    def setUp(self):
        super(CustomMetadataTests, self).setUp()
        self.root_dir = tempfile.mkdtemp(prefix='test-custom-metadata-')
        self.content_dir = os.path.join(self.root_dir, 'content')
        os.makedirs(self.content_dir)

    def tearDown(self):
        super(CustomMetadataTests, self).tearDown()
        shutil.rmtree(self.root_dir)

    def _mock_repo(self, repo_id):
        repo = mock.Mock(spec=Repository)
        repo.id = repo_id
        repo.working_dir = os.path.join(self.root_dir, 'working')
        os.makedirs(repo.working_dir)
        return repo

    def _plugin_config(self, feed_url):
        return mock_conduits.plugin_call_config(feed_url=feed_url)

    # -- custom metadata tests -------------------------------------------------

    def test_presto_delta_custom_metadata(self):
        importer = YumImporter()
        repo = self._mock_repo('test-presto-delta-metadata')
        sync_conduit = mock_conduits.repo_sync_conduit(self.content_dir)
        #feed_url = 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/test_drpm_repo/'
        config = self._plugin_config(TEST_DRPM_REPO_FEED)

        importer._sync_repo(repo, sync_conduit, config)

        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_YUM_REPO_METADATA_FILE])
        metadata_units = sync_conduit.get_units(criteria)

        self.assertEqual(len(metadata_units), 1)

        unit = metadata_units[0]

        self.assertEqual(unit.type_id, TYPE_ID_YUM_REPO_METADATA_FILE)
        self.assertEqual(unit.unit_key['data_type'], 'prestodelta')


