import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0027_remove_checksum_type_field'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0027.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration_fixed_expected_collections(self, mock_connection):
        mock_units_rpm = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_rpm': mock_units_rpm,
        }

        migration.migrate()
        mock_connection.get_database.assert_called_once_with()

        mock_units_rpm.update.assert_called_once_with(
            {"checksum_type": {"$exists": True}},
            {"$unset": {"checksum_type": True}},
            multi=True
        )
