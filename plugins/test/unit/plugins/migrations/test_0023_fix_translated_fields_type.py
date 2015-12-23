import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0023_fix_translated_fields_type'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0023.
    """

    def test_fix_translated_fields_helper_checks_translated_name(self):
        mock_collection = mock.Mock()
        migration.fix_translated_fields_string_to_dict(mock_collection)
        calls = [
            mock.call({'translated_name': ''}, {'$set': {'translated_name': {}}}, multi=True),
            mock.call(
                {'translated_description': ''},
                {'$set': {'translated_description': {}}},
                multi=True
            )
        ]
        mock_collection.update.assert_has_calls(calls=calls)

    @mock.patch(PATH_TO_MODULE + '.fix_translated_fields_string_to_dict')
    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration_fixed_expected_collections(self, mock_connection,
                                                  mock_translated_fields_func):
        mock_units_package_category = mock.Mock()
        mock_units_package_environment = mock.Mock()
        mock_units_package_group = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_package_category': mock_units_package_category,
            'units_package_environment': mock_units_package_environment,
            'units_package_group': mock_units_package_group,
        }
        migration.migrate()
        mock_connection.get_database.assert_called_once_with()
        expected_calls = [
            mock.call(mock_units_package_category),
            mock.call(mock_units_package_environment),
            mock.call(mock_units_package_group),
        ]
        mock_translated_fields_func.assert_has_calls(expected_calls)
