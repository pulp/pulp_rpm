import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0024_errata_pushcount_string'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0022.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration_fixed_expected_collections(self, mock_connection):
        mock_collection = mock.Mock()
        mock_connection.get_database.return_value = {'units_erratum': mock_collection}
        fake_erratum_pushcount_is_null = [
            {'pushcount': None, '_id': 'nullid1'},
            {'pushcount': None, '_id': 'nullid2'},
        ]
        fake_erratum_pushcount_not_null = [
            {'pushcount': 'astring', '_id': 'id1'},
            {'pushcount': 2.0, '_id': 'id2'},
            {'pushcount': 1, '_id': 'id3'},
        ]
        mock_collection.find.side_effect = [
            fake_erratum_pushcount_is_null,
            fake_erratum_pushcount_not_null
        ]
        migration.migrate()
        mock_connection.get_database.assert_called_once_with()
        expected_find_calls = [
            mock.call({'pushcount': {'$type': 10}}, {'pushcount': 1}),
            mock.call({'pushcount': {'$exists': True}}, {'pushcount': 1}),
        ]
        mock_collection.find.assert_has_calls(expected_find_calls)
        expected_update_calls = [
            mock.call({'_id': 'nullid1'}, {'$unset': {'pushcount': ''}}),
            mock.call({'_id': 'nullid2'}, {'$unset': {'pushcount': ''}}),
            mock.call({'_id': 'id2'}, {'$set': {'pushcount': '2'}}),
            mock.call({'_id': 'id3'}, {'$set': {'pushcount': '1'}}),
        ]
        mock_collection.update.assert_has_calls(expected_update_calls)
