import os

from uuid import uuid4
from unittest import TestCase
from urlparse import urljoin

from mock import patch, Mock

from pulp.server.content.sources.model import Request
from pulp_rpm.plugins.importers.yum.repomd.alternate import Packages, ContainerListener


class Unit(object):
    TYPE = 'unit'

    def __init__(self):
        self.unit_key = str(uuid4())
        self.download_path = str(uuid4())
        self.relative_path = str(uuid4())
        self.metadata = {}


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

        # test
        packages = Packages(base_url, nectar_conf, units, dst_dir, listener)

        # validation
        fake_create_downloader.assert_called_with(base_url, nectar_conf)

        self.assertEqual(packages.base_url, base_url)
        self.assertEqual(packages.units, units)
        self.assertEqual(packages.dst_dir, dst_dir)
        self.assertTrue(isinstance(packages.listener, ContainerListener))
        self.assertEqual(packages.listener.content_listener, listener)
        self.assertEqual(packages.primary, fake_create_downloader())
        self.assertEqual(packages.container, fake_container())
        self.assertEqual(packages.canceled, fake_event())

    def test_downloader(self):
        # test
        packages = Packages('http://none', None, [], '', None)

        # validation
        self.assertEqual(packages.downloader, packages)

    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Event', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.create_downloader', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer')
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Packages.get_requests')
    def test_download(self, fake_requests, fake_container):
        listener = Mock()
        base_url = 'http://host'
        units = [
            Unit(),
            Unit(),
            Unit(),
        ]

        # test
        packages = Packages(base_url, None, units, '', listener)
        packages.download_packages()

        # validation
        fake_container().download.assert_called_with(
            packages.canceled, packages.primary, fake_requests(), packages.listener)

    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Event', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.create_downloader', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Request')
    def test_get_requests(self, fake_request):
        listener = Mock()
        base_url = 'http://host'
        units = [
            Unit(),
            Unit(),
            Unit(),
        ]

        # test
        packages = Packages(base_url, None, units, '', listener)
        requests = list(packages.get_requests())

        calls = fake_request.call_args_list
        self.assertEqual(len(requests), len(units))
        for n, call in enumerate(calls):
            self.assertEqual(call[1]['type_id'], units[n].TYPE)
            self.assertEqual(call[1]['unit_key'], units[n].unit_key)
            self.assertEqual(call[1]['url'], urljoin(base_url, units[n].download_path))
            self.assertEqual(call[1]['destination'],
                             os.path.join(packages.dst_dir, units[n].relative_path))
        self.assertEqual(len(requests), len(units))

    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Event', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.create_downloader', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer', Mock())
    @patch('pulp_rpm.plugins.importers.yum.repomd.alternate.Request')
    def test_get_requests_base_url(self, fake_request):
        listener = Mock()
        base_url = 'http://host'
        units = [
            Unit(),
            Unit(),
            Unit(),
        ]
        # set each unit to use a different base url
        for n, unit in enumerate(units):
            unit.metadata['base_url'] = '%s:%s/' % (base_url, n)

        # test
        packages = Packages(base_url, None, units, '', listener)
        requests = list(packages.get_requests())

        calls = fake_request.call_args_list
        self.assertEqual(len(requests), len(units))
        for n, call in enumerate(calls):
            self.assertEqual(call[1]['type_id'], units[n].TYPE)
            self.assertEqual(call[1]['unit_key'], units[n].unit_key)
            unit_base_url = '%s:%s/' % (base_url, n)
            self.assertEqual(call[1]['url'], urljoin(unit_base_url, units[n].download_path))
            self.assertEqual(call[1]['destination'],
                             os.path.join(packages.dst_dir, units[n].relative_path))
        self.assertEqual(len(requests), len(units))

    def test_cancel(self):
        packages = Packages('http://none', None, [], '', None)
        self.assertFalse(packages.canceled.is_set())

        # test
        packages.cancel()

        # validation
        self.assertTrue(packages.canceled.is_set())


class TestListener(TestCase):

    def test_construction(self):
        content_listener = Mock()
        listener = ContainerListener(content_listener)
        self.assertEqual(listener.content_listener, content_listener)

    def test_on_succeeded(self):
        request = Request('T1', {'A': 1}, 'http://test', '/tmp/test')
        request.data = Mock()
        content_listener = Mock()

        # test
        listener = ContainerListener(content_listener)
        listener.on_succeeded(request)

        # validation
        calls = content_listener.download_succeeded.mock_calls
        self.assertEqual(len(calls), 1)
        report = calls[0][1][0]
        self.assertEqual(report.url, request.url)
        self.assertEqual(report.destination, request.destination)
        self.assertEqual(report.data, request.data)

    def test_on_failed(self):
        request = Request('T1', {'A': 1}, 'http://test', '/tmp/test')
        request.data = Mock()
        request.errors = [1, 2, 3]
        content_listener = Mock()

        # test
        listener = ContainerListener(content_listener)
        listener.on_failed(request)

        # validation
        calls = content_listener.download_failed.mock_calls
        self.assertEqual(len(calls), 1)
        report = calls[0][1][0]
        self.assertEqual(report.url, request.url)
        self.assertEqual(report.destination, request.destination)
        self.assertEqual(report.data, request.data)
        self.assertEqual(report.error_report['errors'], request.errors)
