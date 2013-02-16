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
import math
import os
import shutil
import tempfile

from pulp_rpm.common.constants import STATE_COMPLETE, STATE_FAILED, STATE_RUNNING
from pulp_rpm.common.ids import TYPE_ID_ISO
from pulp_rpm.common.sync_progress import SyncProgressReport
from pulp_rpm.plugins.importers.iso_importer.sync import ISOSyncRun
from rpm_support_base import PulpRPMTests
import importer_mocks

from mock import MagicMock, patch
from pulp.common.download.report import DownloadReport
from pulp.plugins.model import Repository, Unit


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
        self.existing_units = [
            Unit(TYPE_ID_ISO, {'name': 'test.iso', 'size': 1, 'checksum': 'sum1'},
                {}, '/path/test.iso'),
            Unit(TYPE_ID_ISO,{'name': 'test2.iso', 'size': 2, 'checksum': 'sum2'},
                {}, '/path/test2.iso'),]
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
        self.assertEqual(iso_sync_run.repo_url, 'http://fake.com/iso_feed/')

        # Inspect the downloader
        downloader = iso_sync_run.downloader
        # The iso_sync_run should be the event listener for the downloader
        self.assertEqual(downloader.event_listener, iso_sync_run)
        # Inspect the downloader config
        expected_downloader_config = {
            'max_speed': 500.0, 'num_threads': 5,
            'ssl_client_cert': "Trust me, I'm who I say I am.",
            'ssl_client_key': 'Secret Key',
            'ssl_ca_cert': "Uh, I guess that's the right server.", 'ssl_verify_host': 1,
            'ssl_verify_peer': 1, 'proxy_url': 'http://proxy.com',
            'proxy_port': 1234,
            'proxy_user': 'the_dude',
            'proxy_password': 'bowling'}
        for key, value in expected_downloader_config.items():
            self.assertEquals(getattr(downloader.config, key), value)
        self.assertEquals(type(iso_sync_run.progress_report), SyncProgressReport)

    def test_cancel_sync(self):
        """
        Test what happens if cancel_sync is called when there is no Bumper.
        """
        # This just passes since the downloader library does not support cancellation. This helps us get one
        # more line of coverage though!
        self.iso_sync_run.cancel_sync()

    def test_download_failed_during_iso_download(self):
        self.iso_sync_run.progress_report.metadata_state = STATE_COMPLETE
        url = 'http://www.theonion.com/articles/american-airlines-us-airways-merge-to-form-worlds,31302/'
        report = DownloadReport(url, '/fake/destination')
        self.iso_sync_run._url_iso_map = {url: {}}

        self.iso_sync_run.download_failed(report)

        # The url shouldn't be in the iso map anymore
        self.assertEqual(self.iso_sync_run._url_iso_map, {})

    def test_download_failed_during_metadata(self):
        self.iso_sync_run.progress_report.metadata_state = STATE_RUNNING
        url = 'http://www.theonion.com/articles/american-airlines-us-airways-merge-to-form-worlds,31302/'
        report = DownloadReport(url, '/fake/destination')
        self.iso_sync_run._url_iso_map = {url: {}}

        self.iso_sync_run.download_failed(report)

        # The url shouldn't be in the iso map anymore, and the metadata_state should be failed
        self.assertEqual(self.iso_sync_run._url_iso_map, {})
        self.assertEqual(self.iso_sync_run.progress_report.metadata_state, STATE_FAILED)

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_failed')
    def test_download_succeeded(self, download_failed):
        destination = StringIO()
        destination.write(
            'Descartes walks into a bar and sits down, the bartender walks up to him and says "You, my man, '
            'look like you need a stiff drink." Descartes considers this, and shakes his head "No, I don\'t '
            'think-" and ceases to exist.')
        unit = 'fake_unit'
        iso = {'name': 'test.txt', 'size': 217, 'destination': destination,
               'checksum': 'a1552efee6f04012bc7e1f3e02c00c6177b08217cead958c47ec83cb8f97f835',
               'unit': unit, 'url': 'http://fake.com'}
        report = DownloadReport(iso['url'], destination)
        # We need to put this on the url_iso_map so that the iso can be retrieved for validation
        self.iso_sync_run._url_iso_map = {iso['url']: iso}
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING

        self.iso_sync_run.download_succeeded(report)

        # The url_iso map should be empty now
        self.assertEqual(self.iso_sync_run._url_iso_map, {})
        # The sync conduit should have been called to save the unit
        self.sync_conduit.save_unit.assert_any_call(unit)
        # The download should not fail
        self.assertEqual(download_failed.call_count, 0)

    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_fails_checksum(self, download_failed):
        destination = StringIO()
        destination.write('What happens when you combine a mosquito with a mountain climber? Nothing. You '
                          'can\'t cross a vector with a scalar.')
        unit = 'fake_unit'
        iso = {'name': 'test.txt', 'size': 114, 'destination': destination,
               'checksum': 'wrong checksum',
               'unit': unit, 'url': 'http://fake.com'}
        report = DownloadReport(iso['url'], destination)
        # We need to put this on the url_iso_map so that the iso can be retrieved for validation
        self.iso_sync_run._url_iso_map = {iso['url']: iso}
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING

        self.iso_sync_run.download_succeeded(report)

        # Because we fail validation, the save_unit step will not be called
        self.assertEqual(self.sync_conduit.save_unit.call_count, 0)
        # The download should be marked failed
        self.assertEqual(download_failed.call_count, 1)
        download_failed.assert_called_once_with(report)

    @patch('pulp.common.download.backends.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.backends.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    @patch('pulp_rpm.plugins.importers.iso_importer.sync.SyncProgressReport', autospec=True)
    def test_perform_sync(self, progress_report, curl_multi, curl):
        """
        Assert that perform_sync() makes appropriate changes to the DB and filesystem.
        """
        repo = MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        repo.working_dir = working_dir

        report = self.iso_sync_run.perform_sync()

        # There should now be three Units in the DB, one for each of the three ISOs that our mocks
        # got us.
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 3)
        expected_units = {
            'test.iso': {
                'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0',
                'size': 16, 'contents': 'This is a file.\n'},
            'test2.iso': {
                'checksum': 'c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16',
                'size': 22, 'contents': 'This is another file.\n'},
            'test3.iso': {
                'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
                'size': 34, 'contents': 'Are you starting to get the idea?\n'}}
        for unit in units:
            expected_unit = expected_units[unit.unit_key['name']]
            self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
            self.assertEqual(unit.unit_key['size'], expected_unit['size'])
            expected_storage_path = os.path.join(
                self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
                str(unit.unit_key['size']), unit.unit_key['name'])
            self.assertEqual(unit.storage_path, expected_storage_path)
            with open(unit.storage_path) as data:
                contents = data.read()
            self.assertEqual(contents, expected_unit['contents'])

    @patch('pulp.common.download.backends.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.backends.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test__download_isos(self, curl_multi, curl):
        # We need to mark the iso_downloader as being in the ISO downloading state
        self.iso_sync_run.progress_report.isos_state = STATE_RUNNING
        # Let's put three ISOs in the manifest
        manifest = [
            {'name': 'test.iso', 'size': 16, 'expected_test_data': 'This is a file.\n',
             'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0',
             'url': 'https://fake.com/test.iso', 'destination': os.path.join(self.pkg_dir, 'test.iso')},
            {'name': 'test2.iso', 'size': 22, 'expected_test_data': 'This is another file.\n', 
             'checksum': 'c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16',
             'url': 'https://fake.com/test2.iso', 'destination': os.path.join(self.pkg_dir, 'test2.iso')},
            {'name': 'test3.iso', 'size': 34, 'expected_test_data': 'Are you starting to get the idea?\n',
             'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
             'url': 'https://fake.com/test3.iso', 'destination': os.path.join(self.pkg_dir, 'test3.iso')},]

        self.iso_sync_run._download_isos(manifest)

        # There should have been two calls to the sync_conduit per ISO, for a total of six calls. Once each to
        # initialize the unit, and once each to save it
        self.assertEqual(self.sync_conduit.init_unit.call_count, 3)
        self.assertEqual(self.sync_conduit.save_unit.call_count, 3)

        for index, iso in enumerate(manifest):
            expected_relative_path = os.path.join(iso['name'], iso['checksum'],
                                                  str(iso['size']), iso['name'])
            self.sync_conduit.init_unit.assert_any_call(
                TYPE_ID_ISO,
                {'name': iso['name'], 'size': iso['size'], 'checksum': iso['checksum']},
                {}, expected_relative_path)
            unit = self.sync_conduit.save_unit.call_args_list[index][0][0]
            self.assertEqual(unit.unit_key['name'], iso['name'])
            self.assertEqual(unit.unit_key['checksum'], iso['checksum'])
            self.assertEqual(unit.unit_key['size'], iso['size'])

            # The file should have been stored at the final destination
            expected_destination = os.path.join(self.pkg_dir, expected_relative_path)
            with open(expected_destination) as written_file:
                self.assertEqual(written_file.read(), iso['expected_test_data'])

    @patch('pulp.common.download.backends.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.backends.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test__download_manifest(self, curl_multi, curl):
        manifest = self.iso_sync_run._download_manifest()

        expected_manifest = [
            {'url': 'http://fake.com/iso_feed/test.iso', 'name': 'test.iso', 'size': 16,
             'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0',},
            {'url': 'http://fake.com/iso_feed/test2.iso', 'name': 'test2.iso', 'size': 22,
             'checksum': 'c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16',},
            {'url': 'http://fake.com/iso_feed/test3.iso', 'name': 'test3.iso', 'size': 34,
             'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',}]

        self.assertEqual(manifest, expected_manifest)

    @patch('pulp.common.download.backends.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @patch('pulp.common.download.backends.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    @patch('pulp_rpm.plugins.importers.iso_importer.sync.ISOSyncRun.download_succeeded',
           side_effect=ISOSyncRun.download_failed)
    def test__download_manifest_failed(self, download_succeeded, curl_multi, curl):
        """
        Make sure we handle the situation correctly when the manifest fails to download.
        """
        download_succeeded.side_effect = self.iso_sync_run.download_failed
        self.iso_sync_run.progress_report.metadata_state = STATE_RUNNING
        try:
            self.iso_sync_run._download_manifest()
            raise Exception()
        except IOError, e:
            self.assertEqual(str(e), 'Could not retrieve http://fake.com/iso_feed/PULP_MANIFEST')
        except Exception, e:
            self.fail('This should have raised an IOError, but it did not.')

    def test__filter_missing_isos(self):
        """
        Make sure this method returns the items from the manifest that weren't in the sync_conduit.
        """
        # Let's put all three mammajammas in the manifest
        manifest = [
            {'name': 'test.iso', 'size': 1, 'checksum': 'sum1'},
            {'name': 'test2.iso', 'size': 2, 'checksum': 'sum2'},
            {'name': 'test3.iso', 'size': 3, 'checksum': 'sum3'},
        ]
        missing_isos = self.iso_sync_run._filter_missing_isos(manifest)

        # Only the third item from the manifest should be missing
        self.assertEqual(missing_isos, [iso for iso in manifest if iso['name'] == 'test3.iso'])

    def test__validate_download_with_regular_file(self):
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write("I heard there was this band called 1023MB, they haven't got any gigs yet.")
        iso = {'name': 'test.txt', 'size': 73, 'destination': destination,
               'checksum': '36891c265290bf4610b488a8eb884d32a29fd17bb9886d899e75f4cf29d3f464'}

        # This should validate, i.e., should not raise any Exception
        self.iso_sync_run._validate_download(iso)

    def test__validate_download_with_stringio(self):
        destination = StringIO()
        destination.write(
            'A neutron walks into a bar. "I\'d like a beer" he says. The bartender promptly serves up a '
            'beer. "How much will that be?" asks the neutron. "For you?" replies the bartender, "no charge".')
        iso = {'name': 'test.txt', 'size': 185, 'destination': destination,
               'checksum': '3c520c6ac45514095021220dab8b8d515bf447bac844573ec01ce20269590574'}

        # This should validate, i.e., should not raise any Exception
        self.iso_sync_run._validate_download(iso)

    def test__validate_download_wrong_checksum(self):
        destination = StringIO()
        destination.write('Two chemists walk into a bar, the first one says "I\'ll have some H2O." to which '
                          'the other adds "I\'ll have some H2O, too." The second chemist died.')
        iso = {'name': 'test.txt', 'size': 146, 'destination': destination,
               'checksum': 'terrible_pun'}

        # This should raise a ValueError with an appropriate error message
        try:
            self.iso_sync_run._validate_download(iso)
            raise Exception()
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed checksum validation. The manifest specified the '
                        'checksum to be terrible_pun, but it was '
                        'dfec884065223f24c3ef333d4c7dcc0eb785a683cfada51ce071410b32a905e8.')
        except Exception:
            self.fail('A ValueError should have been raised, but it was not.')

    def test__validate_download_wrong_size(self):
        destination = StringIO()
        destination.write("Hey girl, what's your sine? It must be math.pi/2 because you're the 1.")
        iso = {'name': 'test.txt', 'size': math.pi, 'destination': destination,
               'checksum': '2b046422425d6f01a920278c55d8842a8989bacaea05b29d1d2082fae91c6041'}

        # This should raise a ValueError with an appropriate error message
        try:
            self.iso_sync_run._validate_download(iso)
            raise Exception()
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed validation. The manifest specified that the '
                        'file should be 3.14159265359 bytes, but the downloaded file is 70 bytes.')
        except Exception:
            self.fail('A ValueError should have been raised, but it was not.')