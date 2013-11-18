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
from tarfile import TarFile
from tempfile import mkdtemp
from urlparse import urlsplit, urlunsplit

from pulp.server.db import connection as db
from pulp.server.db.model.content import ContentCatalog
from pulp.server.managers import factory as managers
from pulp.plugins.conduits.cataloger import CatalogerConduit

from pulp_rpm.plugins.catalogers.yum import YumCataloger, entry_point


TAR_PATH = os.path.join(os.path.dirname(__file__), '../data/cataloger-test-repo.tar')
JSON_PATH = os.path.join(os.path.dirname(__file__), '../data/cataloger-test-repo.json')


class TestCataloger(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        db.initialize('pulp_unittest')
        managers.initialize()
        self.tmp_dir = mkdtemp()
        with TarFile(TAR_PATH) as tar:
            tar.extractall(self.tmp_dir)
        ContentCatalog.get_collection().remove()

    def tearDown(self):
        TestCase.tearDown(self)
        ContentCatalog.get_collection().remove()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_entry_point(self):
        plugin, config = entry_point()
        self.assertEqual(plugin, YumCataloger)
        self.assertEqual(config, {})

    def test_packages(self):
        source_id = 'test'
        config = {'url': 'file://%s/' % self.tmp_dir}
        conduit = CatalogerConduit()
        cataloger = YumCataloger()
        cataloger.refresh(source_id, conduit, config)
        collection = ContentCatalog.get_collection()
        cataloged = list(collection.find())
        with open(JSON_PATH) as fp:
            expected = json.load(fp)
        self.assertEqual(len(cataloged), len(expected))
        for i in range(0, len(expected)):
            for key in ('type_id', 'unit_key', 'locator'):
                self.assertEqual(cataloged[i][key], expected[i][key])
            self.assertUrlEqual(cataloged[i]['url'], expected[i]['url'])

    def assertUrlEqual(self, *urls):
        _urls = list(urls)
        for i in range(0, len(urls)):
            url = urls[i]
            parts = list(urlsplit(url))
            path = list(os.path.split(parts[2]))
            path[0] = 'pulp'  # replace tmp_dir with constant
            parts[2] = os.path.join(*path)
            _urls[i] = urlunsplit(parts)
        for url in _urls:
            for u in _urls:
                self.assertEqual(url, u)