import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0030_remove_errata_unused_fields'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0030.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration(self, mock_connection):
        mock_units_erratum = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_erratum': mock_units_erratum,
        }

        migration.migrate()
        mock_connection.get_database.assert_called_once_with()

        mock_units_erratum.update.assert_called_once_with(
            {'_rpm_references': {'$exists': True}},
            {'$unset': {'_rpm_references': True}},
            multi=True
        )
