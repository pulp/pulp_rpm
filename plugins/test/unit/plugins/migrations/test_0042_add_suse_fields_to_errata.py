import unittest

from pulp.server.db.migrate.models import _import_all_the_way
import mock

migration = _import_all_the_way('pulp_rpm.plugins.migrations.0042_add_suse_'
                                'fields_to_errata')


class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function.
    """
    def setUp(self):
        super(TestMigrate, self).setUp()
        self.errata_need_migration = {
            '_id': '1'
        }

    @mock.patch.object(migration, 'get_collection')
    def test_calls_correct_functions(self, mock_get_collection):
        mock_get_collection.return_value.find.return_value.batch_size.return_value = [
            self.errata_need_migration,
        ]
        migration.migrate()

        self.assertEqual(mock_get_collection.call_count, 1)
        mock_get_collection.return_value.update.assert_any_call(
            {'_id': self.errata_need_migration['_id']},
            {'$set': {'restart_suggested': ''}})
        mock_get_collection.return_value.update.assert_any_call(
            {'_id': self.errata_need_migration['_id']},
            {'$set': {'relogin_suggested': ''}})

    @mock.patch.object(migration, 'get_collection')
    def test_no_migration_called(self, mock_get_collection):
        mock_get_collection.return_value.find.return_value.batch_size.return_value = []
        migration.migrate()

        self.assertEqual(mock_get_collection.call_count, 1)
        mock_get_collection.return_value.update.assert_not_called()
