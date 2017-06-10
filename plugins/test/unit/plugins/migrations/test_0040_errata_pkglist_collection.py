from pulp.common.compat import unittest

import mock

from pymongo.errors import DuplicateKeyError

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0040_errata_pkglist_collection'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch('pulp.server.db.connection.get_database')
@mock.patch.object(migration, 'migrate_erratum_pkglist')
class TestMigrate(unittest.TestCase):
    def test_calls_migrate_erratum_pkglist(self, mock_migrate_pkglist, mock_get_db):
        mock_db = mock_get_db.return_value
        mock_unit = mock.MagicMock()
        mock_erratum_collection = mock_db['units_erratum']
        mock_pkglist_collection = mock_db['erratum_pkglists']
        mock_erratum_collection.find.return_value.batch_size.return_value = [mock_unit]

        migration.migrate()

        self.assertEqual(mock_migrate_pkglist.call_count, 1)
        mock_migrate_pkglist.assert_called_with(mock_erratum_collection, mock_pkglist_collection,
                                                mock_unit)


class TestMigrateErratum(unittest.TestCase):
    def setUp(self):
        super(TestMigrateErratum, self).setUp()
        self.erratum = {
            '_id': '1234',
            'errata_id': 'RHSA:1000',
            'pkglist': [
                # no _pulp_repo_id
                {'name': 'coll_name', 'packages': [{'filename': 'f1'}]},

                # same _pulp_repo_id, different packages (they will be in one pkglist)
                {'name': 'coll_name', '_pulp_repo_id': 'myrepo', 'packages': [{'filename': 'f2'}]},
                {'name': 'coll_name', '_pulp_repo_id': 'myrepo', 'packages': [{'filename': 'f3'}]},

                # no packages
                {'name': 'coll_name', '_pulp_repo_id': 'somerepo', 'packages': []},

                # different _pulp_repo_id, same packages (only last one should be migrated)
                {'name': 'coll_name', '_pulp_repo_id': 'anyrepo', 'packages': [{'filename': 'f4'}]},
                {'name': 'coll_name', '_pulp_repo_id': 'repo', 'packages': [{'filename': 'f4'}]}]
        }
        self.migrated_erratum = {
            '_id': '1235',
            'errata_id': 'RHSA:1010',
            'pkglist': []
        }

    def test_calls_insert(self):
        mock_erratum_collection = mock.MagicMock()
        mock_pkglist_collection = mock.MagicMock()

        migration.migrate_erratum_pkglist(mock_erratum_collection, mock_pkglist_collection,
                                          self.erratum)

        expected_pkglists = [
            {'errata_id': 'RHSA:1000', 'repo_id': 'repo',
             'collections': [{'name': 'coll_name', 'packages': [{'filename': 'f4'}]}]},
            {'errata_id': 'RHSA:1000', 'repo_id': 'myrepo',
             'collections': [{'name': 'coll_name', 'packages': [{'filename': 'f3'}]},
                             {'name': 'coll_name', 'packages': [{'filename': 'f2'}]}]},
            {'errata_id': 'RHSA:1000', 'repo_id': 'somerepo',
             'collections': [{'name': 'coll_name', 'packages': []}]},
            {'errata_id': 'RHSA:1000', 'repo_id': '',
             'collections': [{'name': 'coll_name', 'packages': [{'filename': 'f1'}]}]}]

        mock_pkglist_collection.insert.assert_called_once_with(expected_pkglists)
        mock_erratum_collection.update_one.assert_called_once_with({'_id': '1234'},
                                                                   {'$set': {'pkglist': []}})

    def test_calls_no_insert(self):
        mock_erratum_collection = mock.MagicMock()
        mock_pkglist_collection = mock.MagicMock()

        migration.migrate_erratum_pkglist(mock_erratum_collection, mock_pkglist_collection,
                                          self.migrated_erratum)

        self.assertFalse(mock_pkglist_collection.insert.called)
        self.assertFalse(mock_erratum_collection.update_one.called)

    def test_duplicate_key(self):
        mock_erratum_collection = mock.MagicMock()
        mock_pkglist_collection = mock.MagicMock()
        mock_pkglist_collection.insert.side_effect = DuplicateKeyError('dup')

        migration.migrate_erratum_pkglist(mock_erratum_collection, mock_pkglist_collection,
                                          self.erratum)

        mock_erratum_collection.update_one.assert_called_once_with({'_id': '1234'},
                                                                   {'$set': {'pkglist': []}})
