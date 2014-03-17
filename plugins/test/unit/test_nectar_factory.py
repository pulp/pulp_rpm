# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import mock
import unittest

from nectar.downloaders.local import LocalFileDownloader
from nectar.downloaders.threaded import HTTPThreadedDownloader

from pulp_rpm.plugins.importers.yum.repomd import nectar_factory


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
