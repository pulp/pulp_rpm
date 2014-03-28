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

    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_load_id(self, fake_open):
        fake_fp = Mock()
        fake_fp.read.return_value = 1234
        fake_open.return_value = fake_fp

        # test
        _id = RHUICataloger.load_id()

        # validation
        fake_open.assert_called_with(ID_DOC_URL)
        fake_fp.read.assert_called_witch()
        fake_fp.close.assert_called_with()
        self.assertEqual(_id, fake_fp.read.return_value)

    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_load_id_invalid_url(self, fake_open):
        fake_fp = Mock()
        fake_open.side_effect = URLError('just failed')

        # test
        _id = RHUICataloger.load_id()

        # validation
        fake_open.assert_called_with(ID_DOC_URL)
        self.assertFalse(fake_fp.read.called)
        self.assertFalse(fake_fp.close.called)
        self.assertEqual(_id, None)

    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_load_signature(self, fake_open):
        fake_fp = Mock()
        fake_fp.read.return_value = 1234
        fake_open.return_value = fake_fp

        # test
        signature = RHUICataloger.load_signature()

        # validation
        fake_open.assert_called_with(ID_SIG_URL)
        fake_fp.read.assert_called_witch()
        fake_fp.close.assert_called_with()
        self.assertEqual(signature, fake_fp.read.return_value)

    @patch('pulp_rpm.plugins.catalogers.rhui.urlopen')
    def test_load_signature_invalid_url(self, fake_open):
        fake_fp = Mock()
        fake_open.side_effect = URLError('just failed')

        # test
        signature = RHUICataloger.load_signature()

        # validation
        fake_open.assert_called_with(ID_SIG_URL)
        self.assertFalse(fake_fp.read.called)
        self.assertFalse(fake_fp.close.called)
        self.assertEqual(signature, None)

    @patch('__builtin__.super')
    @patch('pulp_rpm.plugins.catalogers.rhui.RHUICataloger.load_id')
    @patch('pulp_rpm.plugins.catalogers.rhui.RHUICataloger.load_signature')
    def test_nectar_config(self, fake_load_signature, fake_load_id, fake_super):
        config = Mock()
        fake_load_signature.return_value = SIGNATURE
        fake_load_id.return_value = ID
        fake_super().nectar_config.return_value = DownloaderConfig()

        cataloger = RHUICataloger()
        nectar_config = cataloger.nectar_config(config)

        fake_super().nectar_config.assert_called_with(config)

        self.assertEqual(
            nectar_config.headers,
            {ID_DOC_HEADER: urlsafe_b64encode(ID), ID_SIG_HEADER: urlsafe_b64encode(SIGNATURE)})