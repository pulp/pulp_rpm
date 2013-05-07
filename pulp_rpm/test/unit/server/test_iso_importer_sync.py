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
from cStringIO import StringIO
import os
import shutil
import tempfile

from mock import MagicMock, patch
from pulp.common.download.downloaders.curl import HTTPSCurlDownloader
from pulp.common.download.report import DownloadReport
from pulp.plugins.model import Repository, Unit

from pulp_rpm.common import models
from pulp_rpm.common.constants import STATE_COMPLETE, STATE_FAILED, STATE_NOT_STARTED, STATE_RUNNING
from pulp_rpm.common.ids import TYPE_ID_ISO
from pulp_rpm.common.progress import SyncProgressReport
from pulp_rpm.plugins.importers.iso_importer.sync import ISOSyncRun
from rpm_support_base import PulpRPMTests
import importer_mocks


class TestISOSyncRun(PulpRPMTests):
    """
    Test the ISOSyncRun object.
    """
    def setUp(self):
        self.config = importer_mocks.get_basic_config(
            feed_url='http://fake.com/iso_feed/', max_speed=500.0, num_threads=5,
            ssl_client_cert="Trust me, I'm who I say I am.", ssl_client_key="Secret Key",
            ssl_ca_cert="Uh, I guess that's the right server.",
            proxy_url='http://proxy.com', proxy_port=1234, proxy_user="the_dude",
            proxy_password='bowling')

        self.temp_dir = tempfile.mkdtemp()
        self.pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(self.pkg_dir)

        # These checksums correspond to the checksums of the files that our curl mocks will generate. Our
        # curl mocks do not have a test4.iso, so that one is to test removal of old ISOs during sync
        self.existing_units = [
            Unit(TYPE_ID_ISO,
                 {'name': 'test.iso', 'size': 16,
                  'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0'},
                 {}, '/path/test.iso'),
            Unit(TYPE_ID_ISO,
                 {'name': 'test2.iso', 'size': 22,
                  'checksum': 'c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16'},
                 {}, '/path/test2.iso'),
            Unit(TYPE_ID_ISO, {'name': 'test4.iso', 'size': 4, 'checksum': 'sum4'},
                 {}, '/path/test4.iso')]
        self.sync_conduit = importer_mocks.get_sync_conduit(type_id=TYPE_ID_ISO, pkg_dir=self.pkg_dir,
                                                            existing_units=self.existing_units)

        self.iso_sync_run = ISOSyncRun(self.sync_conduit, self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test__init__(self):
        """
        Make sure the __init__ method does cool stuff.
        """
        iso_sync_run = ISOSyncRun(self.sync_conduit, self.config)

        # Now let's assert that all the right things happened during initialization
        self.assertEqual(iso_sync_run.sync_conduit, self.sync_conduit)
        self.assertEqual(iso_sync_run._repo_url, 'http://fake.com/iso_feed/')
        # Validation of downloads should be enabled by default
        self.assertEqual(iso_sync_run._validate_downloads, True)
        # Deleting missing ISOs should be enabled by default
        self.assertEqual(iso_sync_run._remove_missing_units, False)

        # Inspect the downloader
        downloader = iso_sync_run.downloader
        # The iso_sync_run should be the event listener for the downloader
        self.assertEqual(downloader.event_listener, iso_sync_run)
        # Inspect the downloader config
        expected_downloader_config = {
            'max_speed': 500.0, 'num_threads': 5,
            'ssl_client_cert': "Trust me, I'm who I say I am.",
            'ssl_client_key': 'Secret Key',
            'ssl_ca_cert': "Uh, I guess that's the right server.", 'ssl_verify_host': 2,
            'ssl_verify_peer': 1, 'proxy_url': 'http://proxy.com',
            'proxy_port': 1234,
            'proxy_username': 'the_dude',
            'proxy_password': 'bowling'}
        for key, value in expected_downloader_config.items():
            self.assertEquals(getattr(downloader.config, key), value)
        self.assertEquals(type(iso_sync_run.progress_report), SyncProgressReport)

    def test__init___with_feed_lacking_trailing_slash(self):
        """
        In bug https://bugzilla.redhat.com/show_bug.cgi?id=949004 we had a problem where feed URLs that didn't
        have trailing slashes would get their last URL component clobbered when we used urljoin to determine
        the path to PULP_MANIFEST. The solution is to have __init__() automatically append a trailing slash to
        URLs that lack it so that urljoin will determine the correct path to PULP_MANIFEST.
        """
        config = importer_mocks.get_basic_config(feed_url='http://fake.com/no_trailing_slash')

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        # Humorously enough, the _repo_url attribute named no_trailing_slash should now have a trailing slash
        self.assertEqual(iso_sync_run._repo_url, 'http://fake.com/no_trailing_slash/')

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.HTTPSCurlDownloader.cancel',
           side_effect=HTTPSCurlDownloader.cancel, autospec=HTTPSCurlDownloader.cancel)
    def test_cancel_sync(self, cancel):
        """
        Test what happens if cancel_sync is called when there is no Bumper.
        """
        # This just passes since the downloader library does not support cancellation. This helps us get one
        # more line of coverage though!
        self.iso_sync_run.cancel_sync()

        # Assert that the cancel Mock was called
        cancel.assert_called_once_with(self.iso_sync_run.downloader)

    def test_download_failed_during_iso_download(self):
        self.iso_sync_run.progress_report.manifest_state = STATE_COMPLETE
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING
        url = 'http://www.theonion.com/articles/american-airlines-us-airways-merge-to-form-worlds,31302/'
        report = DownloadReport(url, '/fake/destination')
        self.iso_sync_run._url_iso_map = {url: {'name': "fake.iso"}}

        self.iso_sync_run.download_failed(report)

        # The url shouldn't be in the iso map anymore
        self.assertEqual(self.iso_sync_run._url_iso_map, {})

    def test_download_failed_during_manifest(self):
        self.iso_sync_run.progress_report.manifest_state = STATE_RUNNING
        url = 'http://www.theonion.com/articles/american-airlines-us-airways-merge-to-form-worlds,31302/'
        report = DownloadReport(url, '/fake/destination')

        self.iso_sync_run.download_failed(report)

        # The manifest_state should be failed
        self.assertEqual(self.iso_sync_run.progress_report.manifest_state, STATE_FAILED)

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_failed')
    def test_download_succeeded(self, download_failed):
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write(
                'Descartes walks into a bar and sits down, the bartender walks up to him and says "You, my '
                'man, look like you need a stiff drink." Descartes considers this, and shakes his head "No, '
                'I don\'t think-" and ceases to exist.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 217, 'a1552efee6f04012bc7e1f3e02c00c6177b08217cead958c47ec83cb8f97f835',
                         unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination)

        # Simulate having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        # We need to put this on the url_iso_map so that the iso can be retrieved for validation
        self.iso_sync_run._url_iso_map = {iso.url: iso}
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING

        self.iso_sync_run.download_succeeded(report)

        # The url_iso map should be empty now
        self.assertEqual(self.iso_sync_run._url_iso_map, {})
        # The sync conduit should have been called to save the unit
        self.sync_conduit.save_unit.assert_any_call(unit)
        # The download should not fail
        self.assertEqual(download_failed.call_count, 0)

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_honors_validate_units_set_false(self, download_failed):
        """
        We have a setting that makes download validation optional. This test ensures that download_succeeded()
        honors that setting.
        """
        # In this config, we will set validate_units to False, which should make our "wrong_checksum" OK
        config = importer_mocks.get_basic_config(feed_url='http://fake.com/iso_feed/',
                                                 validate_units=False)

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        destination = os.path.join(self.temp_dir, 'test.iso')
        with open(destination, 'w') as test_iso:
            test_iso.write('What happens when you combine a mosquito with a mountain climber? Nothing. You '
                           'can\'t cross a vector with a scalar.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 114, 'wrong checksum', unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination)

        # Let's fake having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        # We need to put this on the url_iso_map so that the iso can be retrieved for validation
        iso_sync_run._url_iso_map = {iso.url: iso}
        iso_sync_run.progress_report.isos_state = STATE_RUNNING

        iso_sync_run.download_succeeded(report)

        # The url_iso map should be empty now
        self.assertEqual(iso_sync_run._url_iso_map, {})
        # The sync conduit should have been called to save the unit
        self.sync_conduit.save_unit.assert_any_call(unit)
        # The download should not fail
        self.assertEqual(download_failed.call_count, 0)

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_honors_validate_units_set_true(self, download_failed):
        """
        We have a setting that makes download validation optional. This test ensures that download_succeeded()
        honors that setting.
        """
        # In this config, we will set validate_units to False, which should make our "wrong_checksum" OK
        config = importer_mocks.get_basic_config(feed_url='http://fake.com/iso_feed/',
                                                 validate_units=True)

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write('Boring test data.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 114, 'wrong checksum', unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination)

        # Let's fake having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        # We need to put this on the url_iso_map so that the iso can be retrieved for validation
        iso_sync_run._url_iso_map = {iso.url: iso}
        iso_sync_run.progress_report.isos_state = STATE_RUNNING

        iso_sync_run.download_succeeded(report)

        # Because we fail validation, the save_unit step will not be called
        self.assertEqual(self.sync_conduit.save_unit.call_count, 0)
        # The download should be marked failed
        self.assertEqual(download_failed.call_count, 1)
        download_failed.assert_called_once_with(report)

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_fails_checksum(self, download_failed):
        """
        This test verifies that download_succeeded does the right thing if the checksum fails. Note
        that we are also implicitly testing that the default behavior is to validate downloads by
        not setting it in this test. There are two other tests that verify that setting the boolean
        explicitly is honored.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write('Boring test data.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 114, 'wrong checksum', unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination)

        # Let's fake having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        # We need to put this on the url_iso_map so that the iso can be retrieved for validation
        self.iso_sync_run._url_iso_map = {iso.url: iso}
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING

        self.iso_sync_run.download_succeeded(report)

        # Because we fail validation, the save_unit step will not be called
        self.assertEqual(self.sync_conduit.save_unit.call_count, 0)
        # The download should be marked failed
        self.assertEqual(download_failed.call_count, 1)
        download_failed.assert_called_once_with(report)

    @patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test_perform_sync(self, curl_multi, curl):
        """
        Assert that perform_sync() makes appropriate changes to the DB and filesystem.
        """
        repo = MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        repo.working_dir = working_dir

        self.iso_sync_run.perform_sync()

        # There should now be three Units in the DB, but only test3.iso is the new one
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
                         'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)
        with open(unit.storage_path) as data:
            contents = data.read()
        self.assertEqual(contents, expected_unit['contents'])
        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is False by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 0)

    @patch('pulp.common.download.downloaders.curl.HTTPSCurlDownloader.download')
    def test_perform_sync_malformed_pulp_manifest(self, download):
        """
        Assert the perform_sync correctly handles the situation when the PULP_MANIFEST file is not in the
        expected format.
        """
        def fake_download(request_list):
            for request in request_list:
                request.destination.write('This is not what a PULP_MANIFEST should look like.')
        download.side_effect = fake_download

        self.iso_sync_run.perform_sync()

        self.assertEquals(type(self.iso_sync_run.progress_report), SyncProgressReport)
        self.assertEqual(self.iso_sync_run.progress_report.manifest_state, STATE_FAILED)
        self.assertEqual(self.iso_sync_run.progress_report.isos_state, STATE_NOT_STARTED)

    @patch('pulp.common.download.downloaders.curl.HTTPSCurlDownloader.download')
    def test_perform_sync_manifest_io_error(self, download):
        """
        Assert the perform_sync correctly handles the situation when retrieving the PULP_MANIFEST file raises an
        IOError.
        """
        download.side_effect = IOError()

        self.iso_sync_run.perform_sync()

        self.assertEquals(type(self.iso_sync_run.progress_report), SyncProgressReport)
        self.assertEqual(self.iso_sync_run.progress_report.manifest_state, STATE_FAILED)
        self.assertEqual(self.iso_sync_run.progress_report.isos_state, STATE_NOT_STARTED)

    @patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test_perform_sync_remove_missing_units_set_false(self, curl_multi, curl):
        # Make sure the missing ISOs don't get removed if they aren't supposed to
        config = importer_mocks.get_basic_config(
            feed_url='http://fake.com/iso_feed/', max_speed=500.0, num_threads=5,
            proxy_url='http://proxy.com', proxy_port=1234, proxy_user="the_dude",
            proxy_password='bowling', remove_missing_units=False,
            ssl_client_cert="Trust me, I'm who I say I am.", ssl_client_key="Secret Key",
            ssl_ca_cert="Uh, I guess that's the right server.")

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        repo = MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        repo.working_dir = working_dir

        report = iso_sync_run.perform_sync()

        # There should now be three Units in the DB
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
                         'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)
        with open(unit.storage_path) as data:
            contents = data.read()
        self.assertEqual(contents, expected_unit['contents'])
        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is False by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 0)

    @patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test_perform_sync_remove_missing_units_set_true(self, curl_multi, curl):
        # Make sure the missing ISOs get removed when they are supposed to
        # Make sure the missing ISOs don't get removed if they aren't supposed to
        config = importer_mocks.get_basic_config(
            feed_url='http://fake.com/iso_feed/', max_speed=500.0, num_threads=5,
            proxy_url='http://proxy.com', proxy_port=1234, proxy_user="the_dude",
            proxy_password='bowling', remove_missing_units=True,
            ssl_client_cert="Trust me, I'm who I say I am.", ssl_client_key="Secret Key",
            ssl_ca_cert="Uh, I guess that's the right server.")

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        repo = MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        repo.working_dir = working_dir

        report = iso_sync_run.perform_sync()

        # There should now be three Units in the DB
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
                         'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)
        with open(unit.storage_path) as data:
            contents = data.read()
        self.assertEqual(contents, expected_unit['contents'])

        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is False by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 1)
        removed_unit = self.sync_conduit.remove_unit.mock_calls[0][1][0]
        self.assertEqual(removed_unit.unit_key, {'name': 'test4.iso', 'size': 4, 'checksum': 'sum4'})

    @patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test__download_isos(self, curl_multi, curl):
        # We need to mark the iso_downloader as being in the ISO downloading state
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING
        # Let's put three ISOs in the manifest
        manifest = StringIO()
        manifest.write('test.iso,f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0,16\n')
        manifest.write('test2.iso,c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16,22\n')
        manifest.write('test3.iso,94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c,34')
        manifest.seek(0)
        manifest = models.ISOManifest(manifest, 'https://fake.com/')
        # Add expected test data to each ISO
        manifest._isos[0].expected_test_data = 'This is a file.\n'
        manifest._isos[1].expected_test_data = 'This is another file.\n'
        manifest._isos[2].expected_test_data = 'Are you starting to get the idea?\n'

        self.iso_sync_run._download_isos(manifest)

        # There should have been two calls to the sync_conduit per ISO, for a total of six calls. Once each to
        # initialize the unit, and once each to save it
        self.assertEqual(self.sync_conduit.init_unit.call_count, 3)
        self.assertEqual(self.sync_conduit.save_unit.call_count, 3)

        for index, iso in enumerate(manifest):
            expected_relative_path = os.path.join(iso.name, iso.checksum,
                                                  str(iso.size), iso.name)
            self.sync_conduit.init_unit.assert_any_call(
                TYPE_ID_ISO,
                {'name': iso.name, 'size': iso.size, 'checksum': iso.checksum},
                {}, expected_relative_path)
            unit = self.sync_conduit.save_unit.call_args_list[index][0][0]
            self.assertEqual(unit.unit_key['name'], iso.name)
            self.assertEqual(unit.unit_key['checksum'], iso.checksum)
            self.assertEqual(unit.unit_key['size'], iso.size)

            # The file should have been stored at the final destination
            expected_destination = os.path.join(self.pkg_dir, expected_relative_path)
            with open(expected_destination) as written_file:
                self.assertEqual(written_file.read(), iso.expected_test_data)

    @patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test__download_manifest(self, curl_multi, curl):
        manifest = self.iso_sync_run._download_manifest()

        expected_manifest_isos = [
            {'url': 'http://fake.com/iso_feed/test.iso', 'name': 'test.iso', 'size': 16,
             'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0'},
            {'url': 'http://fake.com/iso_feed/test2.iso', 'name': 'test2.iso', 'size': 22,
             'checksum': 'c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16'},
            {'url': 'http://fake.com/iso_feed/test3.iso', 'name': 'test3.iso', 'size': 34,
             'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c'}]

        for index, iso in enumerate(manifest):
            self.assertEqual(iso.name, expected_manifest_isos[index]['name'])
            self.assertEqual(iso.url, expected_manifest_isos[index]['url'])
            self.assertEqual(iso.size, expected_manifest_isos[index]['size'])
            self.assertEqual(iso.checksum, expected_manifest_isos[index]['checksum'])

    @patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_succeeded',
           side_effect=ISOSyncRun.download_failed)
    def test__download_manifest_failed(self, download_succeeded, curl_multi, curl):
        """
        Make sure we handle the situation correctly when the manifest fails to download.
        """
        download_succeeded.side_effect = self.iso_sync_run.download_failed
        self.iso_sync_run.progress_report.manifest_state = STATE_RUNNING
        try:
            self.iso_sync_run._download_manifest()
            self.fail('This should have raised an IOError, but it did not.')
        except IOError, e:
            self.assertEqual(str(e), 'Could not retrieve http://fake.com/iso_feed/PULP_MANIFEST')

    @patch('pulp.common.download.downloaders.curl.HTTPSCurlDownloader.download')
    def test__download_manifest_encounters_malformed_manifest(self, download):
        """
        Make sure that _download_manifest raises a ValueError if the PULP_MANIFEST isn't in the expected format.
        """
        def fake_download(request_list):
            for request in request_list:
                request.destination.write('This is not what a PULP_MANIFEST should look like.')
        download.side_effect = fake_download

        try:
            # This should raise a ValueError
            self.iso_sync_run._download_manifest()
            self.fail('A ValueError should have been raised by the previous line, but was not!')
        except ValueError, e:
            # Excellent, a ValueError was raised.
            pass

    def test__filter_missing_isos(self):
        """
        Make sure this method returns the items from the manifest that weren't in the sync_conduit. By
        default, remove_missing_units is False, so we will also assert that the return value of this method
        doesn't suggest removing any ISOs.
        """
        # Let's put all three mammajammas in the manifest
        manifest = ['%s,%s,%s'%(iso.unit_key['name'], iso.unit_key['checksum'], iso.unit_key['size']) \
                    for iso in self.existing_units if iso.unit_key['name'] != 'test4.iso']
        manifest = '\n'.join(manifest)
        manifest = StringIO(manifest)
        manifest = models.ISOManifest(manifest, 'http://test.com')

        local_missing_isos, remote_missing_isos = self.iso_sync_run._filter_missing_isos(manifest)

        # Only the third item from the manifest should be missing locally
        self.assertEqual(local_missing_isos, [iso for iso in manifest if iso.name == 'test3.iso'])
        # The remote repo doesn't have test4.iso, and so this method should tell us
        self.assertEqual(len(remote_missing_isos), 1)
        remote_missing_iso = remote_missing_isos[0]
        self.assertEqual(remote_missing_iso.unit_key, {'name': 'test4.iso', 'size': 4, 'checksum': 'sum4'})
