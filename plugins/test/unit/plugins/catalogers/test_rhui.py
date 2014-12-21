from unittest import TestCase
from urllib2 import URLError
from base64 import urlsafe_b64encode

from mock import patch, Mock
from nectar.config import DownloaderConfig

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.catalogers.rhui import (
    TYPE_ID, RHUICataloger, entry_point, ID_DOC_URL, ID_SIG_URL, ID_DOC_HEADER, ID_SIG_HEADER)


ID = 'test-id'
SIGNATURE = 'test-signature'


class TestCataloger(TestCase):
    def test_entry_point(self):
        plugin, config = entry_point()
        self.assertEqual(plugin, RHUICataloger)
        self.assertEqual(config, {})

    def test_metadata(self):
        md = RHUICataloger.metadata()
        expected = {
            'id': TYPE_ID,
            'display_name': "RHUI Cataloger",
            'types': [models.RPM.TYPE]
        }
        self.assertEqual(md, expected)

    @patch('__builtin__.super')
    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_nectar_config(self, fake_urlopen, fake_super):
        config = Mock()
        fake_fp = Mock()
        fake_fp.read.side_effect = [ID, SIGNATURE]
        fake_urlopen.return_value = fake_fp
        fake_super().nectar_config.return_value = DownloaderConfig()

        cataloger = RHUICataloger()
        nectar_config = cataloger.nectar_config(config)

        fake_super().nectar_config.assert_called_with(config)
        fake_urlopen.assert_any_with(ID_DOC_URL)
        fake_urlopen.assert_any_with(ID_SIG_URL)

        self.assertEqual(fake_urlopen.call_count, 2)
        self.assertEqual(fake_fp.read.call_count, fake_urlopen.call_count)
        self.assertEqual(fake_fp.close.call_count, fake_urlopen.call_count)

        self.assertEqual(
            nectar_config.headers,
            {ID_DOC_HEADER: urlsafe_b64encode(ID), ID_SIG_HEADER: urlsafe_b64encode(SIGNATURE)})

    @patch('__builtin__.super')
    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_nectar_config_raised_getting_id(self, fake_urlopen, fake_super):
        config = Mock()
        fake_urlopen.side_effect = FakeOpener()
        fake_super().nectar_config.return_value = DownloaderConfig()

        cataloger = RHUICataloger()
        self.assertRaises(URLError, cataloger.nectar_config, config)

        fake_super().nectar_config.assert_called_with(config)
        fake_urlopen.assert_called_with(ID_DOC_URL)

        self.assertEqual(fake_urlopen.call_count, 1)

    @patch('__builtin__.super')
    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_nectar_config_raised_getting_signature(self, fake_urlopen, fake_super):
        config = Mock()
        fake_fp = Mock()
        fake_fp.read.side_effect = [ID, SIGNATURE]
        fake_urlopen.side_effect = FakeOpener(2)
        fake_super().nectar_config.return_value = DownloaderConfig()

        cataloger = RHUICataloger()
        self.assertRaises(URLError, cataloger.nectar_config, config)

        fake_super().nectar_config.assert_called_with(config)
        fake_urlopen.assert_any_with(ID_DOC_URL)
        fake_urlopen.assert_any_with(ID_SIG_URL)

        self.assertEqual(fake_urlopen.call_count, 2)


class FakeOpener(object):
    def __init__(self, on_call=1):
        self.on_call = on_call
        self.calls = 0

    def __call__(self, *unused):
        self.calls += 1
        if self.calls == self.on_call:
            raise URLError('go fish')
        fp = Mock()
        fp.read.side_effect = [ID, SIGNATURE]
        return fp
