import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0036_modulo_render_system'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0036.
    """

    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration(self, mock_connection):
        mock_db = mock.Mock()
        mock_connection.get_database.return_value = mock_db
        unit = {
            "repodata": {
                "filelists": "% %",
                "primary": "% %",
                "other": "% %",
            }
        }
        fixed_unit = {
            "repodata": {
                "filelists": "%% %%",
                "primary": "%% %%",
                "other": "%% %%",
            }
        }

        mock_db.units_rpm.find.return_value = [unit]

        migration.migrate()

        mock_connection.get_database.assert_called_once_with()
        mock_db.eval.assert_called_once_with(
            "db.units_rpm.find().forEach(function(e,i) {"
            "e.repodata.filelists=e.repodata.filelists.replace("
            "'{{ pkgid }}','%(pkgid)s');"
            "e.repodata.primary=e.repodata.primary.replace("
            "'{{ checksum }}','%(checksum)s').replace("
            "'{{ checksumtype }}','$(checksumtype)s');"
            "e.repodata.other=e.repodata.other.replace("
            "'{{ pkgid }}','%(pkgid)s');"
            "db.units_rpm.save(e);})")

        mock_db.units_rpm.save.assert_called_once_with(fixed_unit)
