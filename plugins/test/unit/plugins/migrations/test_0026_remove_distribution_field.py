import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0026_remove_distribution_field'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0026.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration_fixed_expected_collections(self, mock_connection):
        mock_units_distribution = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_distribution': mock_units_distribution,
        }

        migration.migrate()
        mock_connection.get_database.assert_called_once_with()

        mock_units_distribution.update.assert_called_once_with(
            {'pulp_distribution_xml_file': {'$exists': True}},
            {'$unset': {'pulp_distribution_xml_file': True}},
            multi=True
        )
