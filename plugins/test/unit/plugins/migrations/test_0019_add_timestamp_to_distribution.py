import os.path
import unittest

from pulp.server.db.migrate.models import _import_all_the_way
import mock


migration = _import_all_the_way('pulp_rpm.plugins.migrations.0019_add_timestamp_'
                                'to_distribution')


class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function.
    """
    @mock.patch.object(migration, 'get_collection')
    def test_calls_correct_functions(self, mock_get_collection):
        """
        """
        mock_get_collection.return_value.find.return_value = [
            fake_distribution1,
        ]

        migration.migrate()

        self.assertEqual(mock_get_collection.call_count, 1)
        mock_get_collection.return_value.update.assert_called_once_with(
            {'_id': fake_distribution1['_id']}, {'$set': {'timestamp': 1354213090.94}},
        )


class TestGetTimestamp(unittest.TestCase):
    def test_treeinfo(self):
        expected = 1354213090.94

        ret = migration._get_timestamp(fake_distribution1)

        self.assertEqual(ret, expected)
        self.assertTrue(isinstance(ret, float))

    def test_dot_treeinfo(self):
        expected = 1354213090.0

        ret = migration._get_timestamp(fake_distribution2)

        self.assertEqual(ret, expected)
        self.assertTrue(isinstance(ret, float))

    def test_no_treeinfo(self):
        ret = migration._get_timestamp(bad_distribution1)

        self.assertEqual(ret, 0.0)
        self.assertTrue(isinstance(ret, float))

    @mock.patch('ConfigParser.RawConfigParser.readfp', side_effect=ValueError)
    def test_unparsable_treeinfo(self, mock_readfp):
        ret = migration._get_timestamp(fake_distribution1)

        self.assertEqual(ret, 0.0)
        self.assertTrue(isinstance(ret, float))


fake_distribution1 = {
    '_id': 'abc123',
    '_storage_path': os.path.join(os.path.dirname(__file__), '../../../data/test_treeinfo/')
}


fake_distribution2 = {
    '_id': 'xyz789',
    '_storage_path': os.path.join(os.path.dirname(__file__), '../../../data/test_dot_treeinfo/')
}


bad_distribution1 = {
    '_id': 'abc123',
    '_storage_path': '/a/b/c/d/e/',
}
