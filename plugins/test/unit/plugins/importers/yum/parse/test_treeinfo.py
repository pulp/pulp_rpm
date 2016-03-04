# -*- coding: utf-8 -*-

import os
import unittest

from mock import patch, MagicMock, Mock
from pulp.server.exceptions import PulpCodedValidationException

from pulp_rpm.common import constants
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.parse.treeinfo import DistSync


DATA_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'data')
DISTRIBUTION_DATA_PATH = os.path.join(DATA_PATH, 'pulp_distribution')
DISTRIBUTION_GOOD_FILE = os.path.join(DISTRIBUTION_DATA_PATH, 'distribution_good.xml')
DISTRIBUTION_BAD_SYNTAX_FILE = os.path.join(DISTRIBUTION_DATA_PATH,
                                            'distribution_bad_xml_syntax.xml')
DISTRIBUTION_BAD_SCHEMA_VALIDATION_FILE = os.path.join(DISTRIBUTION_DATA_PATH,
                                                       'distribution_bad_schema_validation.xml')


class TestRealData(unittest.TestCase):

    def test_rhel5(self):
        path = os.path.join(DATA_PATH, 'treeinfo-rhel5')

        model, files = DistSync.parse_treeinfo_file(path)

        self.assertTrue(isinstance(model, models.Distribution))
        self.assertEqual(model.distribution_id, 'ks-Red Hat Enterprise Linux Server-foo-5.9-x86_64')

        self.assertEqual(len(files), 19)
        for item in files:
            self.assertTrue(item['relativepath'])
        self.assertEquals('foo', model.variant)
        self.assertEquals('Server', model.packagedir)
        self.assertEquals(1354213090.94, model.timestamp)

    def test_rhel5_optional(self):
        path = os.path.join(DATA_PATH, 'treeinfo-rhel5-no-optional-keys')

        model, files = DistSync.parse_treeinfo_file(path)

        self.assertTrue(isinstance(model, models.Distribution))
        self.assertEqual(model.distribution_id, 'ks-Red Hat Enterprise Linux Server-5.9-x86_64')

        self.assertEqual(len(files), 19)
        for item in files:
            self.assertTrue(item['relativepath'])

        self.assertEquals(None, model.variant)
        self.assertEquals(None, model.packagedir)


class TestExistingDistIsCurrent(unittest.TestCase):

    def setUp(self):
        path = os.path.join(DATA_PATH, 'treeinfo-rhel5')

        self.model1, files1 = DistSync.parse_treeinfo_file(path)
        self.model2, files2 = DistSync.parse_treeinfo_file(path)

    def test_current(self):
        ret = DistSync.existing_distribution_is_current(self.model1, self.model2)
        self.assertTrue(ret is True)

    def test_not_current(self):
        self.model1.timestamp = 600.0  # 10 mins after the epoch

        ret = DistSync.existing_distribution_is_current(self.model1, self.model2)

        self.assertTrue(ret is False)

    def test_current_is_none(self):
        self.model1.timestamp = None

        ret = DistSync.existing_distribution_is_current(self.model1, self.model2)

        self.assertTrue(ret is False)

    def test_remote_is_none(self):
        self.model2.timestamp = None

        ret = DistSync.existing_distribution_is_current(self.model1, self.model2)

        self.assertTrue(ret is False)


class TestProcessDistribution(unittest.TestCase):

    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.DistSync.get_distribution_file',
           return_value=DISTRIBUTION_GOOD_FILE)
    def test_parse_good_file(self, mock_get_dist):
        tmp_dir = Mock()
        parent = Mock()
        dist = DistSync(parent, '')
        files = dist.process_distribution(tmp_dir)

        self.assertEquals(3, len(files))
        self.assertEquals('foo/bar.txt', files[0]['relativepath'])
        self.assertEquals('baz/qux.txt', files[1]['relativepath'])
        self.assertEquals(constants.DISTRIBUTION_XML, files[2]['relativepath'])

    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.DistSync.get_distribution_file',
           return_value=None)
    def test_no_distribution(self, mock_get_dist):
        parent = Mock()
        tmp_dir = Mock()
        dist = DistSync(parent, '')
        files = dist.process_distribution(tmp_dir)

        self.assertEquals(0, len(files))

    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.DistSync.get_distribution_file',
           return_value=DISTRIBUTION_BAD_SYNTAX_FILE)
    def test_bad_distribution_syntax(self, mock_get_dist):
        parent = Mock()
        tmp_dir = Mock()
        dist = DistSync(parent, '')
        self.assertRaises(PulpCodedValidationException, dist.process_distribution, tmp_dir)

    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.DistSync.get_distribution_file',
           return_value=DISTRIBUTION_BAD_SCHEMA_VALIDATION_FILE)
    def test_bad_distribution_schema(self, mock_get_dist):
        parent = Mock()
        tmp_dir = Mock()
        dist = DistSync(parent, '')
        self.assertRaises(PulpCodedValidationException, dist.process_distribution, tmp_dir)


class TestGetDistributionFile(unittest.TestCase):
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.nectar_factory.create_downloader')
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.AggregatingEventListener')
    def test_get_distribution_file_exists(self, mock_listener, mock_create_downloader):
        mock_listener.return_value.succeeded_reports = ['foo']
        tmp_dir = '/tmp/'
        feed = 'http://www.foo.bar/flux/'
        parent = Mock(feed=feed)
        dist = DistSync(parent, feed)
        file_name = dist.get_distribution_file(tmp_dir)
        request = mock_create_downloader.return_value.method_calls[0][1][0][0]
        self.assertEquals(request.url, os.path.join(feed, constants.DISTRIBUTION_XML))
        self.assertEquals(request.destination, os.path.join(tmp_dir,
                                                            constants.DISTRIBUTION_XML))
        self.assertEquals(file_name, os.path.join(tmp_dir, constants.DISTRIBUTION_XML))

    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.nectar_factory.create_downloader')
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.AggregatingEventListener')
    def test_get_distribution_file_does_not_exists(self, mock_listener, mock_create_downloader):
        mock_listener.return_value.succeeded_reports = []
        tmp_dir = '/tmp/'
        feed = 'http://www.foo.bar/flux/'
        parent = Mock(feed=feed)
        dist = DistSync(parent, feed)
        file_name = dist.get_distribution_file(tmp_dir)
        self.assertEquals(None, file_name)


class TestParseTreefile(unittest.TestCase):
    """
    This class contains tests for the parse_tree_file() function.
    """

    @patch('__builtin__.open', MagicMock())
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.ConfigParser.RawConfigParser')
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.Distribution')
    def test_sanitizes_checksum_type(self, Distribution, RawConfigParser):
        """
        Ensure the the function properly sanitizes checksum types.
        """
        parser = MagicMock()
        parser.has_section.return_value = True
        parser.items.return_value = [['path', 'sha:checksum']]
        RawConfigParser.return_value = parser

        model, files = DistSync.parse_treeinfo_file('/some/path')

        self.assertEqual(files[0]['checksumtype'], 'sha1')
