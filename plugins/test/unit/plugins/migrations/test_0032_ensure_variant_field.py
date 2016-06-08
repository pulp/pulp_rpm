from unittest import TestCase

from mock import patch

from pulp.server.db.migrate.models import _import_all_the_way


MODULE = 'pulp_rpm.plugins.migrations.0032_ensure_variant_field'

migration = _import_all_the_way(MODULE)


class TestMigrate(TestCase):
    """
    Test migration 0032.
    """

    @patch(MODULE + '.connection.get_collection')
    def test_migration(self, get_collection):
        # test
        migration.migrate()

        # validation
        get_collection.assert_called_once_with('units_distribution')
        get_collection.return_value.update.assert_called_once_with(
            {'$or': [
                {'variant': None},
                {'variant': {'$exists': False}}
            ]},
            {'$set': {'variant': ''}}, multi=True)
