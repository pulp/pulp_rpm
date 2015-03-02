import os
import shutil
import tempfile
import unittest

import mock

from pulp.devel.unit import util
from pulp.server.db.migrate.models import _import_all_the_way


migration = _import_all_the_way('pulp_rpm.plugins.migrations.0021_clean_http_directories')


class TestMigrate(unittest.TestCase):
    """
    Test migration 0021.
    """
    @mock.patch('pulp_rpm.plugins.migrations.0021_clean_http_directories.'
                'configuration')
    @mock.patch('pulp_rpm.plugins.migrations.0021_clean_http_directories.'
                'walk_and_clean_directories')
    def test_walk_correct_directories(self, mock_walk, mock_conf):
        """Migration should check http and https simple serve directories"""
        mock_conf.get_http_publish_dir.return_value = 'http'
        mock_conf.get_https_publish_dir.return_value = 'https'
        migration.migrate()
        mock_walk.assert_has_calls([mock.call('https'), mock.call('http')])

    def setUp(self):
        """Setup a publish base"""
        self.working_dir = tempfile.mkdtemp()
        self.publish_base = os.path.join(self.working_dir, 'publish', 'dir')
        util.touch(os.path.join(self.publish_base, 'listing'))

    def tearDown(self):
        """Cleanup the publish base"""
        shutil.rmtree(self.working_dir, ignore_errors=True)

    @mock.patch('pulp_rpm.plugins.migrations.0021_clean_http_directories.'
                'clean_simple_hosting_directories')
    def test_walk_recognizes_leaf(self, mock_clean):
        """
        Test that an orphaned leaf is detected.
        """
        leaf = os.path.join(self.publish_base, 'a', 'b', 'c', 'listing')
        non_orphan = os.path.join(self.publish_base, 'not', 'leaf', 'listing')
        other_file = os.path.join(self.publish_base, 'not', 'leaf', 'notlisting')
        util.touch(leaf)
        util.touch(non_orphan)
        util.touch(other_file)
        migration.walk_and_clean_directories(self.publish_base)
        expected_leaf = os.path.join(self.publish_base, 'a', 'b', 'c')
        mock_clean.assert_called_once_with(expected_leaf, self.publish_base)

    @mock.patch('pulp_rpm.plugins.migrations.0021_clean_http_directories.'
                'clean_simple_hosting_directories')
    def test_walk_does_not_recognize_non_leaf(self, mock_clean):
        """
        Test that non orphaned leafs are not cleaned.
        """
        non_orphan = os.path.join(self.publish_base, 'not', 'orphan', 'listing')
        other_file = os.path.join(self.publish_base, 'not', 'orphan', 'notlisting')
        util.touch(non_orphan)
        util.touch(other_file)
        migration.walk_and_clean_directories(self.publish_base)
        self.assertEqual(mock_clean.call_count, 0)

    @mock.patch('pulp_rpm.plugins.migrations.0021_clean_http_directories.'
                'clean_simple_hosting_directories')
    def test_walk_does_not_detect_empty_publish_base(self, mock_clean):
        """
        Clean should not be called if there are no directories.
        """
        migration.walk_and_clean_directories(self.publish_base)
        self.assertEqual(mock_clean.call_count, 0)

    def test_clean_ophaned_leaf(self):
        """
        Test that an orphaned leaf is removed.
        """
        leaf = os.path.join(self.publish_base, 'a', 'b', 'c', 'listing')
        leaf_dir = os.path.dirname(leaf)
        util.touch(leaf)
        self.assertTrue(os.path.isfile(leaf))
        migration.clean_simple_hosting_directories(leaf_dir, self.publish_base)
        self.assertFalse(os.path.isdir(os.path.join(self.publish_base, 'a')))

    def test_clean_only_ophaned_leaf(self):
        """
        Test partially shared path, only unshared ophan should be removed.
        """
        leaf = os.path.join(self.publish_base, 'a', 'b', 'c', 'listing')
        non_orphan = os.path.join(self.publish_base, 'a', 'other', 'listing')
        other_file = os.path.join(self.publish_base, 'a', 'other', 'otherfile')
        leaf_dir = os.path.dirname(leaf)
        util.touch(leaf)
        util.touch(non_orphan)
        util.touch(other_file)

        # Not truly necessary, but shows that the files exist before operation.
        self.assertTrue(os.path.isfile(leaf))
        self.assertTrue(os.path.isfile(non_orphan))
        self.assertTrue(os.path.isfile(other_file))
        migration.clean_simple_hosting_directories(leaf_dir, self.publish_base)

        # Show that this dir has been removed.
        self.assertFalse(os.path.isdir(os.path.join(self.publish_base, 'a', 'b')))

        # Non orphan has been preserved.
        self.assertTrue(os.path.isdir(os.path.join(self.publish_base, 'a')))
        self.assertTrue(os.path.isfile(non_orphan))
        self.assertTrue(os.path.isfile(other_file))
