# -*- coding: utf-8 -*-

import os
import unittest

import mock

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.parse import treeinfo


class TestRealData(unittest.TestCase):
    def test_rhel5(self):
        path = os.path.join(os.path.dirname(__file__), '../../../../../data/treeinfo-rhel5')

        model, files = treeinfo.parse_treefile(path)

        self.assertTrue(isinstance(model, models.Distribution))
        self.assertEqual(model.id, 'ks-Red Hat Enterprise Linux Server-foo-5.9-x86_64')

        self.assertEqual(len(files), 19)
        for item in files:
            self.assertTrue(item['relativepath'])
        self.assertEquals('foo', model.variant)
        self.assertEquals('Server', model.metadata[treeinfo.KEY_PACKAGEDIR])

    def test_rhel5_optional(self):
        path = os.path.join(os.path.dirname(__file__),
                            '../../../../../data/treeinfo-rhel5-no-optional-keys')

        model, files = treeinfo.parse_treefile(path)

        self.assertTrue(isinstance(model, models.Distribution))
        self.assertEqual(model.id, 'ks-Red Hat Enterprise Linux Server-5.9-x86_64')

        self.assertEqual(len(files), 19)
        for item in files:
            self.assertTrue(item['relativepath'])

        self.assertEquals(None, model.variant)
        self.assertEquals(None, model.metadata[treeinfo.KEY_PACKAGEDIR])


class TestParseTreefile(unittest.TestCase):
    """
    This class contains tests for the parse_treefile() function.
    """
    @mock.patch('__builtin__.open', mock.MagicMock())
    @mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.ConfigParser.RawConfigParser')
    @mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.models.Distribution')
    def test_sanitizes_checksum_type(self, Distribution, RawConfigParser):
        """
        Ensure the the function properly sanitizes checksum types.
        """
        parser = mock.MagicMock()
        parser.has_section.return_value = True
        parser.items.return_value = [['path', 'sha:checksum']]
        RawConfigParser.return_value = parser

        model, files = treeinfo.parse_treefile('/some/path')

        self.assertEqual(files[0]['checksumtype'], 'sha1')
