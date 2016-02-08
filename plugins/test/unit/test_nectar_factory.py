# -*- coding: utf-8 -*-

import unittest

import mock
from nectar.downloaders.local import LocalFileDownloader
from nectar.downloaders.threaded import HTTPThreadedDownloader

from pulp_rpm.plugins.importers.yum.repomd import nectar_factory


@mock.patch("nectar.downloaders.local.LocalFileDownloader.__init__", mock.Mock(return_value=None))
@mock.patch("nectar.downloaders.threaded.HTTPThreadedDownloader.__init__",
            mock.Mock(return_value=None))
class NectarFactoryTests(unittest.TestCase):
    def setUp(self):
        super(NectarFactoryTests, self).setUp()
        self.mock_config = mock.MagicMock()
        self.mock_event_listener = mock.MagicMock()

    def test_file_url(self):
        downloader = nectar_factory.create_downloader('file:///foo', self.mock_config,
                                                      self.mock_event_listener)
        self.assertTrue(isinstance(downloader, LocalFileDownloader))

    def test_http_url(self):
        downloader = nectar_factory.create_downloader('http://foo', self.mock_config,
                                                      self.mock_event_listener)
        self.assertTrue(isinstance(downloader, HTTPThreadedDownloader))

    def test_https_url(self):
        downloader = nectar_factory.create_downloader('https://foo', self.mock_config,
                                                      self.mock_event_listener)
        self.assertTrue(isinstance(downloader, HTTPThreadedDownloader))

    def test_unknown_scheme(self):
        self.assertRaises(ValueError, nectar_factory.create_downloader, 'foo://bar',
                          self.mock_config, self.mock_event_listener)
