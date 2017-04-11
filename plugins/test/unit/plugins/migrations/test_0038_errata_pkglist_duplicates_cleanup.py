from pulp.common.compat import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0038_errata_pkglist_duplicates_cleanup'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch('pulp.server.db.connection.get_database')
@mock.patch.object(migration, 'migrate_erratum')
class TestMigrate(unittest.TestCase):
    def test_calls_migrate_erratum(self, mock_migrate_erratum, mock_get_db):
        mock_db = mock_get_db.return_value
        mock_unit = mock.MagicMock()
        mock_erratum_collection = mock_db['units_erratum']
        mock_erratum_collection.find.return_value.batch_size.return_value = [mock_unit]

        migration.migrate()

        self.assertEqual(mock_migrate_erratum.call_count, 1)
        mock_migrate_erratum.assert_called_with(mock_erratum_collection, mock_unit)


class TestMigrateErratum(unittest.TestCase):
    def setUp(self):
        super(TestMigrateErratum, self).setUp()
        self.erratum = {
            '_id': '1234',
            'pkglist': [{'name': 'coll_name'},
                        {'name': 'coll_name', '_pulp_repo_id': 'myrepo', 'smth': 1},
                        {'name': 'coll_name', '_pulp_repo_id': 'testrepo'},
                        {'name': 'some_name', '_pulp_repo_id': 'myrepo'},
                        {'name': 'coll_name', '_pulp_repo_id': 'myrepo', 'smth': 2}]
        }

    def test_calls_update(self):
        mock_collection = mock.MagicMock()

        migration.migrate_erratum(mock_collection, self.erratum)

        expected_delta = {
            'pkglist': [{'name': 'coll_name'},
                        {'name': 'coll_name', '_pulp_repo_id': 'testrepo'},
                        {'name': 'some_name', '_pulp_repo_id': 'myrepo'},
                        {'name': 'coll_name', '_pulp_repo_id': 'myrepo', 'smth': 2}]
        }
        mock_collection.update_one.assert_called_once_with({'_id': '1234'},
                                                           {'$set': expected_delta})

    def test_calls_no_update(self):
        mock_collection = mock.MagicMock()
        self.erratum['pkglist'] = [{'name': 'coll_name'},
                                   {'name': 'coll_name', '_pulp_repo_id': 'myrepo', 'smth': 2}]

        migration.migrate_erratum(mock_collection, self.erratum)

        self.assertFalse(mock_collection.update.called)
