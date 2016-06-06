import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0029_remove_rpm_unused_fields'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0029.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration(self, mock_connection):
        mock_units_rpm = mock.Mock()
        mock_connection.get_database.return_value = {
            'units_rpm': mock_units_rpm,
        }

        migration.migrate()
        mock_connection.get_database.assert_called_once_with()
        self.assertEqual(mock_units_rpm.update.call_count, 2)
        expected_calls = [
            mock.call({'filelist': {'$exists': True}}, {'$unset': {'filelist': True}}, multi=True),
            mock.call({'_erratum_references': {'$exists': True}},
                      {'$unset': {'_erratum_references': True}}, multi=True)
        ]
        mock_units_rpm.update.assert_has_calls(expected_calls)
