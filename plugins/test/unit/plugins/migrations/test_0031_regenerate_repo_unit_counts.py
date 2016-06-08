import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0031_regenerate_repo_unit_counts'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test migration 0031.
    """

    @mock.patch(PATH_TO_MODULE + '.rebuild_content_unit_counts')
    @mock.patch(PATH_TO_MODULE + '.connection')
    def test_migration(self, mock_connection, mock_rebuild_content_unit_counts):
        mock_repos = mock.Mock()
        mock_db = {'repos': mock_repos}
        mock_connection.get_database.return_value = mock_db
        mock_repo_id = mock.Mock()
        mock_repo = {'repo_id': mock_repo_id}
        mock_repos.find.return_value = [mock_repo]

        migration.migrate()

        mock_rebuild_content_unit_counts.assert_called_once_with(mock_db, mock_repo_id)

    def test_rebuild_content_unit_counts(self):
        faketype = 'faketype'
        count = 100
        mock_q = {
            'result': [{
                '_id': faketype,
                'sum': count,
            }]
        }

        class MockDatabase(dict):
            command = mock.Mock(return_value=mock_q)
        mock_repos = mock.Mock()
        mock_db = MockDatabase()
        mock_db['repos'] = mock_repos
        mock_repo_id = mock.Mock()

        migration.rebuild_content_unit_counts(mock_db, mock_repo_id)

        mock_db.command.assert_called_once_with(
            'aggregate', 'repo_content_units',
            pipeline=[
                {'$match': {'repo_id': mock_repo_id}},
                {'$group': {'sum': {'$sum': 1}, '_id': '$unit_type_id'}}
            ]
        )
        mock_repos.update_one.assert_called_once_with(
            {'repo_id': mock_repo_id},
            {'$set': {'content_unit_counts': {faketype: count}}}
        )
