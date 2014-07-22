
import os

from uuid import uuid4
from unittest import TestCase
from urlparse import urljoin

from mock import patch, Mock, ANY

from nectar.report import DownloadReport

from pulp.server.content.sources.model import Request
from pulp_rpm.plugins.importers.yum.repomd.alternate import Packages, ContainerListener


class Unit(object):

    TYPE = 'unit'

    def __init__(self):
        self.unit_key = str(uuid4())
        self.download_path = str(uuid4())
        self.relative_path = str(uuid4())


class TestPackages(TestCase):

    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Event')
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer')
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.create_downloader')
    def test_construction(self, fake_create_downloader, fake_container, fake_event):
        base_url = str(uuid4())
        nectar_conf = Mock()
        units = Mock()
        dst_dir = str(uuid4())
        listener = Mock()

        packages = Packages(base_url, nectar_conf, units, dst_dir, listener)

        fake_create_downloader.assert_called_with(base_url, nectar_conf)

        self.assertEqual(packages.base_url, base_url)
        self.assertEqual(packages.units, units)
        self.assertEqual(packages.dst_dir, dst_dir)
        self.assertEqual(packages.listener, listener)
        self.assertEqual(packages.primary, fake_create_downloader())
        self.assertEqual(packages.container, fake_container())
        self.assertEqual(packages.canceled, fake_event())

    def test_downloader(self):
        packages = Packages('http://none', None, [], '', None)
        self.assertEqual(packages.downloader, packages)

    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Event', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.create_downloader', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer.download')
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContainerListener')
    def test_download(self, fake_listener, fake_download):
        listener = Mock()
        fake_listener.return_value = listener
        base_url = 'http://host'
        units = [
            Unit(),
            Unit(),
            Unit(),
        ]

        packages = Packages(base_url, None, units, '', Mock())
        packages.download_packages()

        fake_listener.assert_called_with(packages.listener)
        fake_download.assert_called_with(packages.canceled, packages.primary, ANY, listener)

        calls = fake_download.mock_calls
        self.assertEqual(len(calls), 1)
        requests = calls[0][1][2]
        self.assertEqual(len(requests), len(units))
        for n, request in enumerate(requests):
            self.assertTrue(isinstance(request, Request))
            self.assertEqual(request.type_id, units[n].TYPE)
            self.assertEqual(request.unit_key, units[n].unit_key)
            self.assertEqual(request.url, urljoin(base_url, units[n].download_path))
            self.assertEqual(request.destination, os.path.join(packages.dst_dir, units[n].relative_path))

    def test_caneel(self):
        packages = Packages('http://none', None, [], '', None)
        self.assertFalse(packages.canceled.is_set())
        packages.cancel()
        self.assertTrue(packages.canceled.is_set())


class TestListener(TestCase):

    def test_construction(self):
        content_listener = Mock()
        listener = ContainerListener(content_listener)
        self.assertEqual(listener.content_listener, content_listener)

    def test_download_succeeded(self):
        request = Request('T1', {'A': 1}, 'http://test', '/tmp/test')
        request.data = Mock()
        content_listener = Mock()

        listener = ContainerListener(content_listener)
        listener.download_succeeded(request)

        calls = content_listener.download_succeeded.mock_calls
        self.assertEqual(len(calls), 1)
        report = calls[0][1][0]
        self.assertEqual(report.url, request.url)
        self.assertEqual(report.destination, request.destination)
        self.assertEqual(report.data, request.data)

    def test_download_failed(self):
        request = Request('T1', {'A': 1}, 'http://test', '/tmp/test')
        request.data = Mock()
        request.errors = [1, 2, 3]
        content_listener = Mock()

        listener = ContainerListener(content_listener)
        listener.download_failed(request)

        calls = content_listener.download_failed.mock_calls
        self.assertEqual(len(calls), 1)
        report = calls[0][1][0]
        self.assertEqual(report.url, request.url)
        self.assertEqual(report.destination, request.destination)
        self.assertEqual(report.data, request.data)
        self.assertEqual(report.error_report['errors'], request.errors)