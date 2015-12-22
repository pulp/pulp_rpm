import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0022_rename_unit_id_fields'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0022.
    """

    @mock.patch(PATH_TO_MODULE + '._drop_and_silence_exception')
    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration_fixed_expected_collections(self, mock_connection,
                                                  mock__drop_and_silence_exception):
        mock_units_distribution = mock.Mock()
        mock_units_erratum = mock.Mock()
        mock_units_package_category = mock.Mock()
        mock_units_package_environment = mock.Mock()
        mock_units_package_group = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_distribution': mock_units_distribution,
            'units_erratum': mock_units_erratum,
            'units_package_category': mock_units_package_category,
            'units_package_environment': mock_units_package_environment,
            'units_package_group': mock_units_package_group,
        }
        migration.migrate()
        mock_connection.get_database.assert_called_once_with()

        mock_units_distribution.update.assert_called_once_with(
            {}, {'$rename': {'id': 'distribution_id'}})
        mock_units_erratum.update.assert_has_calls([
            mock.call({}, {'$rename': {'id': 'errata_id'}}),
            mock.call({}, {'$rename': {'from': 'errata_from'}})
        ])
        mock_units_package_category.update.assert_called_once_with(
            {}, {'$rename': {'id': 'package_category_id'}}
        )
        mock_units_package_environment.update.assert_called_once_with(
            {}, {'$rename': {'id': 'package_environment_id'}}
        )
        mock_units_package_group.update.assert_called_once_with(
            {}, {'$rename': {'id': 'package_group_id'}}
        )

        expected_calls = [
            mock.call(mock_units_distribution, 'id_1'),
            mock.call(mock_units_distribution, 'id_1_family_1_variant_1_version_1_arch_1'),
            mock.call(mock_units_erratum, 'id_1'),
            mock.call(mock_units_package_group, 'id_1'),
            mock.call(mock_units_package_group, 'id_1_repo_id_1'),
            mock.call(mock_units_package_category, 'id_1'),
            mock.call(mock_units_package_category, 'id_1_repo_id_1'),
            mock.call(mock_units_package_environment, 'id_1'),
            mock.call(mock_units_package_environment, 'id_1_repo_id_1'),
        ]
        mock__drop_and_silence_exception.assert_has_calls(expected_calls)

    def test__drop_and_silence_exception_drops_index_name(self):
        mock_collection = mock.Mock()
        mock_index_name = mock.Mock()
        migration._drop_and_silence_exception(mock_collection, mock_index_name)
        mock_collection.drop_index.assert_called_once_with(mock_index_name)

    def test__drop_and_silence_exception_silences_operation_failure(self):
        mock_collection = mock.Mock()
        mock_collection.drop_index.side_effect = migration.OperationFailure('error')
        try:
            migration._drop_and_silence_exception(mock_collection, mock.Mock())
        except Exception:
            self.fail('_drop_and_silence_exception did not silence OperationFailure')

    def test__drop_and_silence_exception_does_not_silence_other_exceptions(self):
        mock_collection = mock.Mock()
        mock_collection.drop_index.side_effect = IOError()
        self.assertRaises(IOError, migration._drop_and_silence_exception,
                          mock_collection, mock.Mock())
