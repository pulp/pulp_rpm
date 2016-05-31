"""
pulp_rpm.plugins.migrations.0031_yum_metadata_storage_path
"""
import unittest

from mock import Mock, patch

from pulp.server.db.migrate.models import _import_all_the_way

from pulp_rpm.plugins.db import models

PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0031_yum_metadata_storage_path'

migration = _import_all_the_way(PATH_TO_MODULE)


class Test0031YumMetadataStoragePath(unittest.TestCase):
    """
    Test the migration of the yum_repo_metadata_file storage path re-calculation.
    """
    @patch('__builtin__.open', autospec=True)
    @patch(PATH_TO_MODULE + '.model.Distributor.objects')
    @patch(PATH_TO_MODULE + '.models.YumMetadataFile.objects')
    def test_migration(self, mock_metadata, mock_dist, mock_open):
        metadata_foo = models.YumMetadataFile(data_type='product-id', repo_id='foo')
        metadata_foo._storage_path = 'a/b/c'
        metadata_foo.set_storage_path = Mock()
        metadata_foo.save = Mock()
        mock_metadata.filter.return_value = [metadata_foo]

        migration.migrate()

        self.assertFalse(metadata_foo.save.called)
        mock_dist.filter.assert_called_once_with(repo_id__in=set([]), last_publish__ne=None)

    @patch('__builtin__.open', autospec=True)
    @patch(PATH_TO_MODULE + '.model.Distributor.objects')
    @patch(PATH_TO_MODULE + '.models.YumMetadataFile.objects')
    def test_migration_storage_path(self, mock_metadata, mock_dist, mock_open):
        metadata_foo = models.YumMetadataFile(data_type='product-id', repo_id='foo')
        metadata_foo._storage_path = 'a/b/c'
        metadata_foo.save = Mock()
        metadata_foo.safe_import_content = Mock()
        mock_metadata.filter.return_value = [metadata_foo]

        migration.migrate()

        metadata_foo.save.assert_called_once_with()
        metadata_foo.safe_import_content.assert_called_once_with('a/b/c')
        mock_dist.filter.assert_called_once_with(repo_id__in=set(['foo']), last_publish__ne=None)
