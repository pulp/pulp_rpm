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
import tempfile

import mock

from pulp.plugins.model import Repository
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp_rpm.common.ids import TYPE_ID_YUM_REPO_METADATA_FILE
from yum_importer.importer import YumImporter

import mock_conduits
import rpm_support_base


class CustomMetadataTests(rpm_support_base.PulpRPMTests):

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
        repo.working_dir = os.path.join(self.root_dir, repo_id, 'working')
        os.makedirs(repo.working_dir)
        return repo

    def _plugin_config(self, feed_url):
        return mock_conduits.plugin_call_config(feed_url=feed_url)

    # -- custom metadata tests -------------------------------------------------

    def test_presto_delta_custom_metadata(self):
        importer = YumImporter()
        repo = self._mock_repo('test-presto-delta-metadata')
        sync_conduit = mock_conduits.repo_sync_conduit(self.content_dir)
        feed_url = "http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/test_drpm_repo/"
        config = self._plugin_config(feed_url)

        try:
            importer._sync_repo(repo, sync_conduit, config)

        except Exception, e:
            self.fail(str(e))

        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_YUM_REPO_METADATA_FILE])
        metadata_units = sync_conduit.get_unit(criteria)

        self.assertTrue(len(metadata_units) > 1)
