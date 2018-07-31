import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way

migration = _import_all_the_way('pulp_rpm.plugins.migrations.0043_populate_recommends')


class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function
    """
    @mock.patch.object(migration, 'utils')
    @mock.patch.object(migration, 'migrate_rpm')
    @mock.patch.object(migration, 'get_collection')
    def test_calls_correct_functions(self, mock_get_collection, mock_migrate_rpm, mock_utils):
        find_mock = mock_get_collection.return_value.find
        batch_size_mock = find_mock.return_value.batch_size
        # fake cursor
        selection_mock = batch_size_mock.return_value = mock.MagicMock()
        unit_mock = mock.MagicMock()
        selection_mock.__iter__.return_value = [unit_mock]

        migration.migrate()
        mock_get_collection.assert_called_once_with('units_rpm')
        find_mock.assert_called_once_with(
            {'recommends': {'$exists': False}}, ['repodata.primary']
        )
        batch_size_mock.assert_called_once_with(100)
        count_mock = batch_size_mock.return_value.count
        count_mock.assert_called_once_with()
        mock_utils.MigrationProgressLog.assert_called_once_with('RPM', count_mock.return_value)
        progress_log_mock = mock_utils.MigrationProgressLog.return_value.__enter__.return_value
        mock_migrate_rpm.assert_called_once_with(mock_get_collection.return_value, unit_mock)
        progress_log_mock.progress.assert_called_once_with()


class TestMigrateRpm(unittest.TestCase):
    """
    Test the migrate_rpm() function
    """
    def setUp(self):
        super(TestMigrateRpm, self).setUp()
        self.collection_mock = mock.Mock()
        # fake a dict
        self.unit_mock = mock.MagicMock()

    @mock.patch.object(migration, 'ET')
    @mock.patch.object(migration, 'gzip')
    @mock.patch.object(migration, '_HEADER')
    def test_calls_correct_functions(self, mock__HEADER, mock_gzip, mock_ET):
        root_element_mock = mock_ET.fromstring.return_value

        root_element_mock.iterfind.return_value = [
            self.unit_mock,
        ]
        migration.migrate_rpm(self.collection_mock, self.unit_mock)
        self.unit_mock.get.assert_called_once_with('repodata', {})
        repodata_mock = self.unit_mock.get.return_value
        repodata_mock.get.assert_called_once_with('primary', '')
        primary_mock = repodata_mock.get.return_value
        mock_gzip.zlib.decompress.assert_called_once_with(primary_mock)
        decompress_mock = mock_gzip.zlib.decompress.return_value
        mock__HEADER.format.assert_called_once_with(decompress_mock)
        primary_xml_mock = mock__HEADER.format.return_value
        mock_ET.fromstring.assert_called_once_with(primary_xml_mock)
        root_element_mock.iterfind.assert_called_once_with(
            './common:package/common:format/rpm:recommends/rpm:entry', migration._NAMESPACES
        )
        self.collection_mock.update_one.assert_called_once_with(
            {'_id': self.unit_mock['_id']},
            {'$set': {'recommends': [self.unit_mock.attrib]}}
        )

    @mock.patch.object(migration, 'ET')
    @mock.patch.object(migration, 'gzip')
    @mock.patch.object(migration, '_HEADER')
    def test_no_update(self, _, __, mock_ET):
        root_element_mock = mock_ET.fromstring.return_value
        root_element_mock.iterfind.return_value = []
        migration.migrate_rpm(self.collection_mock, self.unit_mock)
        self.collection_mock.update_one.assert_not_called()
