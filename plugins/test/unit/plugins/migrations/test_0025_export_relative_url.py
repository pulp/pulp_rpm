import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way

PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0025_export_relative_url'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch(PATH_TO_MODULE + '.connection')
class TestMigrate(unittest.TestCase):
    """
    Test migration 0025
    """

    def test_migration_export_relative_url(self, connection):
        repo_collection = self._build_repo_data()
        repo_distributor_collection = self._build_pre_migration_data()
        connection.get_database.return_value = {'repos': repo_collection,
                                                'repo_distributors': repo_distributor_collection}
        migration.migrate()
        repo_update = {"$set": {
            "config": {
                "http": False,
                "https": True,
                "relative_url": "repos/pulp/pulp/demo_repos/zoo/"
            }}}

        expected_update_calls = [
            mock.call({'_id': 'fake_yum_distributor'}, repo_update),
            mock.call({'_id': 'fake_export_distributor'}, repo_update),
        ]
        repo_distributor_collection.update_one.assert_has_calls(expected_update_calls)

    def test_migration_export_idepotency(self, connection):
        repo_collection = self._build_repo_data()
        repo_distributor_collection = self._build_post_migration_data()
        connection.get_database.return_value = {'repos': repo_collection,
                                                'repo_distributors': repo_distributor_collection}
        migration.migrate()
        assert not repo_distributor_collection.update_one.called

    def _build_repo_data(self):
        collection = mock.Mock()
        collection.find.side_effect = [[{"repo_id": "zoo"}]]
        return collection

    def _build_pre_migration_data(self):
        collection = mock.Mock()
        collection_side_effect = [{
            "_id": "fake_yum_distributor",
            "repo_id": "zoo",
            "distributor_id": "yum_distributor",
            "distributor_type_id": "yum_distributor",
            "config": {
                "http": False,
                "https": True,
                "relative_url": "/repos/pulp/pulp/demo_repos/zoo/"
            }
        }, {
            "_id": "fake_export_distributor",
            "repo_id": "zoo",
            "distributor_id": "export_distributor",
            "distributor_type_id": "export_distributor",
            "config": {
                "http": False,
                "https": True,
            }
        }]
        collection.find.side_effect = [collection_side_effect]
        return collection

    def _build_post_migration_data(self):
        collection = mock.Mock()
        collection_side_effect = [{
            "_id": "fake_yum_distributor",
            "repo_id": "zoo",
            "distributor_id": "yum_distributor",
            "distributor_type_id": "yum_distributor",
            "config": {
                "http": False,
                "https": True,
                "relative_url": "repos/pulp/pulp/demo_repos/zoo/"
            }
        }, {
            "_id": "fake_export_distributor",
            "repo_id": "zoo",
            "distributor_id": "export_distributor",
            "distributor_type_id": "export_distributor",
            "config": {
                "http": False,
                "https": True,
                "relative_url": "repos/pulp/pulp/demo_repos/zoo/"
            }
        }]
        collection.find.side_effect = [collection_side_effect]
        return collection
