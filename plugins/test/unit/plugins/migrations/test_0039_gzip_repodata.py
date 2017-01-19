import copy
import gzip

import bson
import mock

from pulp.common.compat import unittest
from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0039_gzip_repodata'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch('pulp.server.db.connection.get_database')
@mock.patch.object(migration, 'migrate_rpm_base')
class TestMigrate(unittest.TestCase):
    def test_calls_migrate_rpm_base(self, mock_migrate_rpm_base, mock_get_db):
        mock_db = mock_get_db.return_value
        mock_unit = mock.MagicMock()
        mock_rpm_collection = mock_db['units_rpm']
        mock_rpm_collection.find.return_value.batch_size.return_value = [mock_unit]
        mock_srpm_collection = mock_db['units_srpm']
        mock_srpm_collection.find.return_value.batch_size.return_value = [mock_unit]

        migration.migrate()

        self.assertEqual(mock_migrate_rpm_base.call_count, 2)
        mock_migrate_rpm_base.assert_called_with(mock_rpm_collection, mock_unit)
        mock_migrate_rpm_base.assert_called_with(mock_srpm_collection, mock_unit)


class TestMigrateRPMBase(unittest.TestCase):
    def setUp(self):
        super(TestMigrateRPMBase, self).setUp()
        self.repodata = {'primary': u'\u041f\u0440\u0438\u0432\u0435\u0442! stuff',
                         'filelists': u'\u041f\u0440\u0438\u0432\u0435\u0442! stuff',
                         'other': u'\u041f\u0440\u0438\u0432\u0435\u0442! stuff'}

    def test_calls_update(self):
        mock_collection = mock.MagicMock()
        self.rpm = {
            '_id': '1234',
            'repodata': copy.copy(self.repodata)
        }

        migration.migrate_rpm_base(mock_collection, self.rpm)

        expected_delta = {'repodata': {}}
        for mtype, metadata in self.rpm['repodata'].items():
            compressed_metadata = gzip.zlib.compress(metadata.encode('utf-8'))
            expected_delta['repodata'][mtype] = bson.binary.Binary(compressed_metadata)

        mock_collection.update_one.assert_called_once_with({'_id': '1234'},
                                                           {'$set': expected_delta})

    def test_rerun_migration(self):
        mock_collection = mock.MagicMock()
        self.rpm = {
            '_id': '1234',
            'repodata': copy.copy(self.repodata)
        }

        for mtype, metadata in self.rpm['repodata'].items():
            compressed_metadata = gzip.zlib.compress(metadata.encode('utf-8'))
            self.rpm['repodata'][mtype] = bson.binary.Binary(compressed_metadata)

        migration.migrate_rpm_base(mock_collection, self.rpm)

        self.assertFalse(mock_collection.update_one.called)
