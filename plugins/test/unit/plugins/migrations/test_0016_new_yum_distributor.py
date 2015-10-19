import datetime
import os
import tempfile
import shutil
import uuid

import mock
from pulp.common import dateutils
from pulp.server import config as pulp_config
from pulp.server.db.migrate.models import _import_all_the_way
from pulp.server.db import models
from pulp.server.db.model.repository import RepoDistributor

from pulp_rpm.devel import rpm_support_base


MIGRATION_MODULE = 'pulp_rpm.plugins.migrations.0016_new_yum_distributor'


class BaseMigrationTests(rpm_support_base.PulpRPMTests):
    def setUp(self):
        super(BaseMigrationTests, self).setUp()

        self.distributors_collection = RepoDistributor.get_collection()

        self.root_test_dir = tempfile.mkdtemp(prefix='test_0016_migration_')
        self.http_publish_dir = os.path.join(self.root_test_dir, 'http', 'repos')
        self.https_publish_dir = os.path.join(self.root_test_dir, 'https', 'repos')

        self.migration_module = _import_all_the_way(MIGRATION_MODULE)

    def tearDown(self):
        super(BaseMigrationTests, self).tearDown()

        models.Repository.drop_collection()
        self.distributors_collection.drop()

        shutil.rmtree(self.root_test_dir, ignore_errors=True)

    # -- test data setup -------------------------------------------------------

    def _generate_repo(self, repo_id):
        repo_model = models.Repository(repo_id=repo_id, display_name=repo_id)
        repo_model.save()
        return repo_model

    def _generate_distributor(self, repo_id, config=None, previously_published=True):
        config = config or {}
        distributor_id = str(uuid.uuid4())
        distributor_model = RepoDistributor(repo_id, distributor_id, 'yum_distributor', config,
                                            True)
        if previously_published:
            distributor_model['last_published'] = dateutils.format_iso8601_datetime(
                datetime.datetime.now())
        self.distributors_collection.insert(distributor_model)
        return self.distributors_collection.find_one({'id': distributor_id})

    @staticmethod
    def _touch(path):
        try:
            handle = open(path, 'w')
            handle.close()
        except:
            pass


class HelperMethodTests(BaseMigrationTests):
    def test_clear_working_dir(self):

        sub_dirs = ['one/two/', 'three/']

        for d in sub_dirs:
            path = os.path.join(self.root_test_dir, d)
            os.makedirs(path)
            self._touch(os.path.join(path, 'test_file'))

        for d in sub_dirs:
            path = os.path.join(self.root_test_dir, d)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.exists(os.path.join(path, 'test_file')))

        self.migration_module._clear_working_dir({'id': 'test_repo'}, self.root_test_dir)

        for d in sub_dirs:
            path = os.path.join(self.root_test_dir, d)
            self.assertFalse(os.path.exists(path))
            self.assertFalse(os.path.exists(os.path.join(path, 'test_file')))

    def test_clear_old_publish_dirs_http(self):

        orig_clear_orphaned_dirs = self.migration_module._clear_orphaned_publish_dirs
        self.migration_module._clear_orphaned_publish_dirs = mock.MagicMock()

        repo_id = 'test_repo'
        repo = self._generate_repo(repo_id)

        publish_path = os.path.join(self.http_publish_dir, 'foo', repo_id)
        os.makedirs(os.path.join(publish_path, 'repodata'))

        self.assertTrue(os.path.exists(publish_path))
        self.assertTrue(os.path.exists(os.path.join(publish_path, 'repodata')))

        config = {'http_publish_dir': self.http_publish_dir,
                  'relative_url': 'foo/' + repo_id}

        self.migration_module._clear_old_publish_dirs(repo, config)

        self.assertFalse(os.path.exists(publish_path))
        self.assertFalse(os.path.exists(os.path.join(publish_path, 'repodata')))

        self.migration_module._clear_orphaned_publish_dirs.assert_called_once_with(
            self.http_publish_dir, os.path.join(self.http_publish_dir, 'foo'))

        self.migration_module._clear_orphaned_publish_dirs = orig_clear_orphaned_dirs

    def test_clear_old_publish_dirs_https(self):

        orig_clear_orphaned_dirs = self.migration_module._clear_orphaned_publish_dirs
        self.migration_module._clear_orphaned_publish_dirs = mock.MagicMock()

        repo_id = 'test_repo'
        repo = self._generate_repo(repo_id)

        publish_path = os.path.join(self.https_publish_dir, 'foo', repo_id)
        os.makedirs(os.path.join(publish_path, 'repodata'))

        self.assertTrue(os.path.exists(publish_path))
        self.assertTrue(os.path.exists(os.path.join(publish_path, 'repodata')))

        config = {'https_publish_dir': self.https_publish_dir,
                  'relative_url': 'foo/' + repo_id}

        self.migration_module._clear_old_publish_dirs(repo, config)

        self.assertFalse(os.path.exists(publish_path))
        self.assertFalse(os.path.exists(os.path.join(publish_path, 'repodata')))

        self.migration_module._clear_orphaned_publish_dirs.assert_called_once_with(
            self.https_publish_dir, os.path.join(self.https_publish_dir, 'foo'))

        self.migration_module._clear_orphaned_publish_dirs = orig_clear_orphaned_dirs

    def test_clear_orphaned_publish_dirs(self):

        sub_directory_path_elements = ['one', 'two', 'three']

        path = self.root_test_dir[:]

        for e in sub_directory_path_elements:
            path = os.path.join(path, e)
            os.makedirs(path)
            self._touch(os.path.join(path, 'listing'))

        self.migration_module._clear_orphaned_publish_dirs(
            self.root_test_dir, os.path.join(self.root_test_dir, *sub_directory_path_elements))

        path = self.root_test_dir[:]

        self.assertTrue(os.path.exists(path))

        for e in sub_directory_path_elements:
            path = os.path.join(path, e)
            self.assertFalse(os.path.exists(path))
            self.assertFalse(os.path.exists(os.path.join(path, 'listing')))

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher.get_working_dir')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher.publish')
    def test_re_publish_repository(self, mock_publish, m_wd):

        repo_id = 'test_repo'
        repo = self._generate_repo(repo_id)
        dist = self._generate_distributor(repo_id)

        self.migration_module._re_publish_repository(repo, dist)

        mock_publish.assert_called_once()

    def test_distributor_working_dir(self):
        distributor_id = 'distid'
        repo_id = 'repoid'
        storage_dir = pulp_config.config.get('server', 'storage_dir')
        actual_dir = '%s/working/repos/%s/distributors/%s' % (storage_dir, repo_id, distributor_id)
        directory = self.migration_module.distributor_working_dir(distributor_id, repo_id,
                                                                  mkdir=False)
        self.assertEqual(actual_dir, directory)

    @mock.patch('os.makedirs')
    def test_distributor_working_dir_makedirs(self, mock_makedirs):
        distributor_id = 'distid'
        repo_id = 'repoid'
        storage_dir = pulp_config.config.get('server', 'storage_dir')
        distributor_working_dir = '%s/working/repos/%s/distributors/%s' % (storage_dir, repo_id,
                                                                           distributor_id)
        directory = self.migration_module.distributor_working_dir(distributor_id, repo_id)
        mock_makedirs.assert_has_calls([mock.call(distributor_working_dir)])
        self.assertEqual(distributor_working_dir, directory)


class MigrationTests(BaseMigrationTests):
    def setUp(self):
        super(MigrationTests, self).setUp()

        self.orig_clear_working_dir = self.migration_module._clear_working_dir
        self.orig_clear_old_publish_dirs = self.migration_module._clear_old_publish_dirs
        self.orig_re_publish_repository = self.migration_module._re_publish_repository
        self.orig_remove_legacy_publish_dirs = self.migration_module._remove_legacy_publish_dirs

        self.migration_module._clear_working_dir = mock.MagicMock()
        self.migration_module._clear_old_publish_dirs = mock.MagicMock()
        self.migration_module._remove_legacy_publish_dirs = mock.MagicMock()
        self.migration_module._re_publish_repository = mock.MagicMock()

    def tearDown(self):
        super(MigrationTests, self).tearDown()

        self.migration_module._clear_working_dir = self.orig_clear_working_dir
        self.migration_module._clear_old_publish_dirs = self.orig_clear_old_publish_dirs
        self.migration_module._re_publish_repository = self.orig_re_publish_repository
        self.migration_module._remove_legacy_publish_dirs = self.orig_remove_legacy_publish_dirs

    @mock.patch('pulp.plugins.loader.api._is_initialized', return_value=True)
    def test_migrate(self, mock_is_init):
        repo_id = 'test_repo'
        config = {'relative_url': '/this/way/to/the/test_repo'}

        self._generate_repo(repo_id)
        self._generate_distributor(repo_id, config)

        self.migration_module.migrate()

        self.migration_module._clear_working_dir.assert_called_once()
        self.migration_module._clear_old_publish_dirs.assert_called_once()
        self.migration_module._re_publish_repository.assert_called_once()
        self.migration_module._remove_legacy_publish_dirs.assert_called_once()

    @mock.patch('pulp.plugins.loader.api._is_initialized', return_value=True)
    @mock.patch('pulp.plugins.loader.api.initialize')
    def test_migrate_already_initialized(self, mock_init, mock_is_init):
        with mock.patch.object(self.migration_module, 'get_collection') as mock_get_collection:
            mock_get_collection.return_value.find.return_value = []

            self.migration_module.migrate()

            mock_is_init.assert_called_once_with()
            self.assertEqual(mock_init.call_count, 0)

    @mock.patch('pulp.plugins.loader.api._is_initialized', return_value=False)
    @mock.patch('pulp.plugins.loader.api.initialize')
    def test_migrate_not_initialized(self, mock_init, mock_is_init):
        with mock.patch.object(self.migration_module, 'get_collection') as mock_get_collection:
            mock_get_collection.return_value.find.return_value = []

            self.migration_module.migrate()

            mock_is_init.assert_called_once_with()
            mock_init.assert_called_once_with()
