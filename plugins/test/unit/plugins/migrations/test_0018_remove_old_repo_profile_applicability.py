"""
This module contains unit tests for
pulp_rpm.plugins.migrations.0018_remove_old_repo_profile_applicability.

"""
import unittest

from pulp.server.db.migrate.models import _import_all_the_way
import mock

migration = _import_all_the_way('pulp_rpm.plugins.migrations.0018_remove_old_'
                                'repo_profile_applicability')


class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function.
    """
    @mock.patch('pulp_rpm.plugins.migrations.0018_remove_old_repo_profile_applicability.'
                'connection.get_collection')
    def test_calls_correct_functions(self, get_collection):
        """
        Assert that migrate() drops the collection it should
        """
        fake_rpa = mock.Mock()
        get_collection.return_value = fake_rpa

        migration.migrate()

        get_collection.assert_called_once_with('repo_profile_applicability')
        fake_rpa.drop.assert_called_once_with()
