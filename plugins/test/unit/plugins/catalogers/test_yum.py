import os
import json
import shutil
from unittest import TestCase
from tarfile import TarFile
from tempfile import mkdtemp
from urlparse import urlsplit, urlunsplit
from contextlib import closing

from mock import patch, Mock

from pulp.server.managers import factory as managers
from pulp.plugins.conduits.cataloger import CatalogerConduit

from pulp_rpm.plugins.catalogers.yum import TYPE_ID, YumCataloger, entry_point
from pulp_rpm.plugins.db.models import RPM


TAR_PATH = os.path.join(os.path.dirname(__file__), '../../../data/cataloger-test-repo.tar')
JSON_PATH = os.path.join(os.path.dirname(__file__), '../../../data/cataloger-test-repo.json')

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

    def test_metadata(self):
        md = YumCataloger.metadata()
        expected = {
            'id': TYPE_ID,
            'display_name': "Yum Cataloger",
            'types': [RPM._content_type_id.default]
        }
        self.assertEqual(md, expected)

    @patch('pulp_rpm.plugins.catalogers.yum.nectar_factory')
    def test_get_downloader(self, fake_factory):
        url = 'my-url'
        conduit = Mock()
        config = Mock()
        fake_downloader = Mock()
        fake_factory.create_downloader.return_value = fake_downloader

        cataloger = YumCataloger()
        cataloger.nectar_config = Mock()
        downloader = cataloger.get_downloader(conduit, config, url)

        fake_factory.create_downloader.assert_called_with(url, cataloger.nectar_config())
        self.assertEqual(downloader, fake_downloader)

    @patch('pulp.server.managers.content.catalog.ContentCatalogManager.add_entry')
    def test_refresh(self, mock_add):
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

    @patch('pulp_rpm.plugins.catalogers.yum.descriptor')
    def test_nectar_config(self, fake_descriptor):
        config = Mock()
        fake_config = Mock()
        fake_descriptor.nectar_config.return_value = fake_config

        cataloger = YumCataloger()
        nectar_config = cataloger.nectar_config(config)

        fake_descriptor.nectar_config.assert_called_with(config)
        self.assertEqual(nectar_config, fake_config)
