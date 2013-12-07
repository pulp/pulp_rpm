# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os

import json
import shutil

from unittest import TestCase
from mock import patch
from tarfile import TarFile
from tempfile import mkdtemp
from urlparse import urlsplit, urlunsplit
from contextlib import closing

from pulp.server.managers import factory as managers
from pulp.plugins.conduits.cataloger import CatalogerConduit

from pulp_rpm.plugins.catalogers.yum import YumCataloger, entry_point


TAR_PATH = os.path.join(os.path.dirname(__file__), '../data/cataloger-test-repo.tar')
JSON_PATH = os.path.join(os.path.dirname(__file__), '../data/cataloger-test-repo.json')

SOURCE_ID = 'test'
EXPIRES = 90


class TestCataloger(TestCase):

    @staticmethod
    def _normalized(url):
        parts = list(urlsplit(url))
        path = list(os.path.split(parts[2]))
        path[0] = 'pulp'  # replace tmp_dir with constant
        parts[2] = os.path.join(*path)
        return urlunsplit(parts)

    def setUp(self):
        TestCase.setUp(self)
        managers.initialize()
        self.tmp_dir = mkdtemp()
        with closing(TarFile(TAR_PATH)) as tar:
            tar.extractall(self.tmp_dir)

    def tearDown(self):
        TestCase.tearDown(self)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_entry_point(self):
        plugin, config = entry_point()
        self.assertEqual(plugin, YumCataloger)
        self.assertEqual(config, {})

    @patch('pulp.server.managers.content.catalog.ContentCatalogManager.add_entry')
    def test_packages(self, mock_add):
        url = 'file://%s/' % self.tmp_dir
        conduit = CatalogerConduit(SOURCE_ID, EXPIRES)
        cataloger = YumCataloger()
        cataloger.refresh(conduit, {}, url)
        with open(JSON_PATH) as fp:
            expected = json.load(fp)
        self.assertEqual(mock_add.call_count, len(expected))
        for entry in expected:
            self.assertTrue(
                mock_add.called_with(
                    SOURCE_ID,
                    EXPIRES,
                    entry['type_id'],
                    entry['unit_key'],
                    self._normalized(entry['url'])))

