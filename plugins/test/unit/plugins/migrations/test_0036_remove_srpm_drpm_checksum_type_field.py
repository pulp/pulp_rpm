import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0036_remove_srpm_drpm_checksum_type_field'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0036.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration(self, mock_connection):
        mock_units_srpm = mock.Mock()
        mock_units_drpm = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_srpm': mock_units_srpm, 'units_drpm': mock_units_drpm
        }

        migration.migrate()
        mock_connection.get_database.assert_called_once_with()
        self.assertEqual(mock_units_srpm.update.call_count, 1)
        self.assertEqual(mock_units_drpm.update.call_count, 1)
        expected_calls = [
            mock.call({'checksum_type': {'$exists': True}},
                      {'$unset': {'checksum_type': True}}, multi=True)
        ]
        mock_units_srpm.update.assert_has_calls(expected_calls)
        mock_units_drpm.update.assert_has_calls(expected_calls)
