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

import datetime
import os
import tempfile
import shutil
import uuid

import mock

from pulp.common import dateutils
from pulp.server.db.migrate.models import _import_all_the_way
from pulp.server.db.model.repository import Repo, RepoDistributor

import rpm_support_base


MIGRATION_MODULE = 'pulp_rpm.migrations.0015_new_yum_distributor'


class NewYumDistributorMigrationTests(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(NewYumDistributorMigrationTests, self).setUp()

        self.repos_collection = Repo.get_collection()
        self.distributors_collection = RepoDistributor.get_collection()

        self.root_test_dir = tempfile.mkdtemp(prefix='test_0015_migration_')

        self.migration_module = _import_all_the_way(MIGRATION_MODULE)
        self.migration_module.REPO_WORKING_DIR = os.path.join(self.root_test_dir, 'working', '%s')
        self.migration_module.OLD_HTTP_PUBLISH_DIR = os.path.join(self.root_test_dir, 'http', 'repos')
        self.migration_module.OLD_HTTPS_PUBLISH_DIR = os.path.join(self.root_test_dir, 'https', 'repos')

    def tearDown(self):
        super(NewYumDistributorMigrationTests, self).tearDown()

        self.repos_collection.drop()
        self.distributors_collection.drop()

        shutil.rmtree(self.root_test_dir, ignore_errors=True)

    # -- test data setup -------------------------------------------------------

    def _generate_repo(self, repo_id):
        repo_model = Repo(repo_id, repo_id)
        self.repos_collection.insert(repo_model)

        os.makedirs(self.migration_module.REPO_WORKING_DIR % repo_id + '/metadata/')

        return repo_model

    def _generate_distributor(self, repo_id, config=None, previously_published=True):
        config = config or {}

        distributor_id = str(uuid.uuid4())
        distributor_model = RepoDistributor(repo_id, distributor_id, 'yum_distributor', config, True)
        if previously_published:
            distributor_model['last_published'] = dateutils.format_iso8601_datetime(datetime.datetime.now())
        self.distributors_collection.insert(distributor_model)

        http_publish_dir = config.get('http_publish_dir', self.migration_module.OLD_HTTP_PUBLISH_DIR)
        https_publish_dir = config.get('https_publish_dir', self.migration_module.OLD_HTTPS_PUBLIST_DIR)
        relative_path = config.get('relative_url', repo_id)
        if config.get('http', False):
            os.makedirs(os.path.join(http_publish_dir, relative_path))
            self._touch(os.path.join(http_publish_dir, 'listing'))
        if config.get('https', False):
            os.makedirs(os.path.join(https_publish_dir, relative_path))
            self._touch(os.path.join(https_publish_dir, 'listing'))

        return distributor_model

    @staticmethod
    def _touch(path):
        try:
            handle = open(path, 'w')
            handle.close()
        except:
            pass

    # -- tests -----------------------------------------------------------------

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_https_only(self, mock_publish):
        repo_id = 'test_repo'
        repo = self._generate_repo(repo_id)

        config = {'https': True}
        distributor = self._generate_distributor(repo_id, config)

        # make sure the test data was created correctly
        self.assertTrue(os.path.exists(os.path.join(self.migration_module.REPO_WORKING_DIR % repo_id + '/metadata/')))
        self.assertTrue(os.path.exists(os.path.join(self.migration_module.OLD_HTTPS_PUBLISH_DIR, repo_id)))
        self.assertTrue(os.path.exists(os.path.join(self.migration_module.OLD_HTTPS_PUBLISH_DIR, 'listing')))

        self.migration_module.migrate()

        # make sure the working directory was cleared out
        working_contents = os.listdir(os.path.join(self.migration_module.REPO_WORKING_DIR % repo_id))
        self.assertEqual(len(working_contents), 0)

        # make sure the publish directory was cleared out
        self.assertFalse(os.path.exists(os.path.join(self.migration_module.OLD_HTTPS_PUBLISH_DIR, repo_id)))
        self.assertFalse(os.path.exists(os.path.join(self.migration_module.OLD_HTTPS_PUBLISH_DIR, 'listing')))

        # make sure the repo was re-published
        mock_publish.assert_called_once_with(repo_id, distributor['id'])

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_http_and_https(self, mock_publish):
        pass

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_custom_relative_path(self, mock_publish):
        pass

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_never_published(self, mock_publish):
        pass

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_published_no_publish_dir(self, mock_publish):
        pass

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_two_distributors(self, mock_publish):
        pass

    @mock.patch('pulp.server.managers.repo.publish.RepoPublishManager.publish')
    def test_multiple_repos(self, mock_publish):
        pass

