import tempfile
import os
import shutil
import unittest

from pulp.devel.unit import util
from pulp.server.db.migrate.models import _import_all_the_way
import mock


migration = _import_all_the_way('pulp_rpm.plugins.migrations.0020_nested_drpm_directory')
DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../data/')


class TestMigrate(unittest.TestCase):

    def setUp(self):
        # Create the sample environment
        self.working_dir = tempfile.mkdtemp()

        # Create the nested drpm directory
        drpm_foo = os.path.join(self.working_dir, 'drpms', 'drpms', 'foo.drpm')
        util.touch(os.path.join(drpm_foo))

        # create the repomd files & prestodelta files
        self.repodata_dir = os.path.join(self.working_dir, 'repodata')
        os.makedirs(self.repodata_dir)
        self.good_presto = os.path.join(self.working_dir, 'repodata', 'good-prestodelta.xml.gz')
        util.touch(self.good_presto)
        self.bad_presto = os.path.join(self.working_dir, 'repodata', 'bad-prestodelta.xml.gz')
        os.symlink(drpm_foo, self.bad_presto)
        shutil.copy(os.path.join(DATA_DIR, 'repomd_double_drpm.xml'),
                    os.path.join(self.repodata_dir, 'repomd.xml'))

        # create a fake nested repo directory from a distribution
        os.makedirs(os.path.join(self.working_dir, 'foo', 'repodata'))
        os.symlink(drpm_foo, os.path.join(self.working_dir, 'foo', 'repodata', 'repomd.xml'))

    def tearDown(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def test_get_repo_directories(self):
        """
        Test that the generator for getting the repos only gets the real repo and not
        a nested repo from a distribution
        """
        repolist = list(migration._repo_directories(self.working_dir))
        self.assertEquals([self.working_dir], repolist)

    def test_move_nested_drpm_dir(self):
        """
        Test that if there is a nested drpm/drpm/ directory we will remove it
        """
        migration._move_nested_drpm_dir(self.working_dir)
        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'drpms', 'foo.drpm')))
        self.assertFalse(os.path.exists(os.path.join(self.working_dir, 'drpms', 'drpms')))

    def test_move_nested_drpm_dir_no_processing(self):
        """
        Test that the processor does not fail if the nested rpm/drpm directory doesn't exist.
        """
        shutil.rmtree(os.path.join(self.working_dir, 'drpms', 'drpms'))
        migration._move_nested_drpm_dir(self.working_dir)
        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'drpms')))

    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_remove_prestodelta_from_repomd')
    def test_remove_prestodelta_symlinks(self, mock_remove_from_repomd):
        """
        Test that any symlinks to prestodelta files in the repodata directory are removed
        since they are old references to bad files.
        """
        migration._remove_prestodelta_symlinks(self.working_dir)
        self.assertTrue(os.path.exists(self.good_presto))
        self.assertFalse(os.path.exists(self.bad_presto))
        mock_remove_from_repomd.assert_called_once_with(self.working_dir, 'bad-prestodelta.xml.gz')

    def test_remove_prestodelta_symlinks_no_processing(self):
        """
        Test that things still work if there is no work to be done.
        """
        os.unlink(self.bad_presto)
        migration._remove_prestodelta_symlinks(self.working_dir)
        self.assertTrue(os.path.exists(self.good_presto))

    def test_remove_prestodelta_from_repomd(self):
        """
        Make sure that the the removal of the prestodelta from the repomd.xml works properly.
        """
        migration._remove_prestodelta_from_repomd(self.working_dir, 'bad-prestodelta.xml.gz')

        with open(os.path.join(self.repodata_dir, 'repomd.xml')) as repomd:
            content = repomd.read()
            if content.find('bad-prestodelta.xml.gz') != -1:
                raise Exception("bad presto wasn't remove")

            if content.find('good-prestodelta.xml.gz') == -1:
                raise Exception("good presto was removed improperly")

    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                'get_collection')
    def test_remove_prestodelta_repo_units(self, mock_get_collection):
        """
        Test removing the prestodelta units from the database.
        """
        mock_unit_collection = mock.Mock()
        mock_repo_unit_collection = mock.Mock()
        mock_get_collection.side_effect = util.SideEffect(mock_unit_collection,
                                                          mock_repo_unit_collection)
        mock_unit_collection.find.return_value = [{'_id': 'foo'}]

        migration._remove_prestodelta_repo_units()

        mock_unit_collection.find.assert_called_once_with({'data_type': 'prestodelta'})
        mock_repo_unit_collection.remove.assert_called_once_with({'unit_id': 'foo'})

    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_remove_prestodelta_repo_units')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_remove_prestodelta_symlinks')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_move_nested_drpm_dir')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_repo_directories')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                'config')
    def test_migrate_workflow(self, mock_config, mock_directories, mock_move,
                              mock_remove_symlinks, mock_remove_units):
        """
        Test the overall workflow of the migration.
        1. Get the repos to migrate
        2. Migrate each individual repository
        3. Remove the references from the database
        """

        yum_publish_dir = os.path.join(self.working_dir, 'published', 'yum', 'master')
        os.makedirs(yum_publish_dir)
        mock_config.get.return_value = self.working_dir
        mock_directories.return_value = ['foo']

        migration.migrate()

        mock_move.assert_called_once_with('foo')
        mock_remove_symlinks.assert_called_once_with('foo')
        mock_remove_units.assert_called_once_with()

    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_remove_prestodelta_repo_units')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_repo_directories')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                'config')
    def test_migrate_workflow_no_published_repos(self, mock_config, mock_directories,
                                                 mock_remove_units):
        """
        Test the overall workflow of the migration if the master dir exists but is empty.
        """

        yum_publish_dir = os.path.join(self.working_dir, 'published', 'yum', 'master')
        os.makedirs(yum_publish_dir)
        mock_config.get.return_value = self.working_dir
        mock_directories.return_value = []

        migration.migrate()

        mock_remove_units.assert_called_once_with()

    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                '_remove_prestodelta_repo_units')
    @mock.patch('pulp_rpm.plugins.migrations.0020_nested_drpm_directory.'
                'config')
    def test_migrate_workflow_no_master_dir(self, mock_config, mock_remove_units):
        """
        Test the overall workflow of the migration if the published dir does not exist.
        In this case only the database cleaning will take place.
        """

        mock_config.get.return_value = self.working_dir

        migration.migrate()

        mock_remove_units.assert_called_once_with()
