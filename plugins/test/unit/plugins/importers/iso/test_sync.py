from cStringIO import StringIO
import os
import shutil
import tempfile

from mock import MagicMock, patch
from nectar.downloaders.threaded import HTTPThreadedDownloader
from nectar.report import DownloadReport
from pulp.common.plugins import importer_constants
from pulp.plugins.model import Repository, Unit
from pulp.server import constants as server_constants

from pulp_rpm.common.ids import TYPE_ID_ISO
from pulp_rpm.common.progress import SyncProgressReport, ISOProgressReport
from pulp_rpm.devel import importer_mocks
from pulp_rpm.devel.rpm_support_base import PulpRPMTests
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.iso.sync import ISOSyncRun


class TestISOSyncRun(PulpRPMTests):
    """
    Test the ISOSyncRun object.
    """

    def fake_download(self, requests):
        requests = list(requests)
        req = requests[0]
        try:
            # try to write the manifest data
            req.destination.write(
                'test.iso,f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0,16\n'
                'test2.iso,c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16,22\n'
                'test3.iso,94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c,34'
            )
        except AttributeError:
            # this happens for all requests except the manifest
            pass

        reports = []
        for r in requests:
            # pretend everything worked great
            report = DownloadReport(r.url, r.destination, r.data)
            self.iso_sync_run.download_succeeded(report)
            reports.append(report)

    def setUp(self):
        config = {
            importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
            importer_constants.KEY_MAX_SPEED: 500.0,
            importer_constants.KEY_MAX_DOWNLOADS: 5,
            importer_constants.KEY_SSL_VALIDATION: False,
            importer_constants.KEY_SSL_CLIENT_CERT: "Trust me, I'm who I say I am.",
            importer_constants.KEY_SSL_CLIENT_KEY: "Secret Key",
            importer_constants.KEY_SSL_CA_CERT: "Uh, I guess that's the right server.",
            importer_constants.KEY_PROXY_HOST: 'proxy.com',
            importer_constants.KEY_PROXY_PORT: 1234,
            importer_constants.KEY_PROXY_USER: "the_dude",
            importer_constants.KEY_PROXY_PASS: 'bowling',
            importer_constants.KEY_VALIDATE: False,
        }

        self.config = importer_mocks.get_basic_config(**config)

        self.temp_dir = tempfile.mkdtemp()
        self.pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(self.pkg_dir)

        # These checksums correspond to the checksums of the files that our curl mocks will
        # generate. Our curl mocks do not have a test4.iso, so that one is to test removal of
        # old ISOs during sync
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
        self.sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=self.pkg_dir,
                                                            existing_units=self.existing_units,
                                                            pulp_units=self.existing_units)

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
        # Validation of downloads should be disabled by default
        self.assertEqual(iso_sync_run._validate_downloads, False)
        # Deleting missing ISOs should be enabled by default
        self.assertEqual(iso_sync_run._remove_missing_units, False)

        # Inspect the downloader
        downloader = iso_sync_run.downloader
        # The iso_sync_run should be the event listener for the downloader
        self.assertEqual(downloader.event_listener, iso_sync_run)
        # Inspect the downloader config
        expected_downloader_config = {
            'max_speed': 500.0, 'max_concurrent': 5,
            'ssl_client_cert': "Trust me, I'm who I say I am.",
            'ssl_client_key': 'Secret Key',
            'ssl_ca_cert': "Uh, I guess that's the right server.", 'ssl_validation': False,
            'proxy_url': 'proxy.com',
            'proxy_port': 1234,
            'proxy_username': 'the_dude',
            'proxy_password': 'bowling'}
        for key, value in expected_downloader_config.items():
            self.assertEquals(getattr(downloader.config, key), value)
        self.assertEquals(type(iso_sync_run.progress_report), SyncProgressReport)

    def test__init___ssl_validation(self):
        """
        Make sure the SSL validation is on by default.
        """
        # It should default to True
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: 'http://fake.com/iso_feed/'})
        iso_sync_run = ISOSyncRun(self.sync_conduit, config)
        self.assertEqual(iso_sync_run.downloader.config.ssl_validation, True)

        # It should be possible to explicitly set it to False
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
               importer_constants.KEY_SSL_VALIDATION: False})
        iso_sync_run = ISOSyncRun(self.sync_conduit, config)
        self.assertEqual(iso_sync_run.downloader.config.ssl_validation, False)

        # It should be possible to explicitly set it to True
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
               importer_constants.KEY_SSL_VALIDATION: True})
        iso_sync_run = ISOSyncRun(self.sync_conduit, config)
        self.assertEqual(iso_sync_run.downloader.config.ssl_validation, True)

    def test__init___with_feed_lacking_trailing_slash(self):
        """
        In bug https://bugzilla.redhat.com/show_bug.cgi?id=949004 we had a problem where feed
        URLs that didn't
        have trailing slashes would get their last URL component clobbered when we used urljoin
        to determine
        the path to PULP_MANIFEST. The solution is to have __init__() automatically append a
        trailing slash to
        URLs that lack it so that urljoin will determine the correct path to PULP_MANIFEST.
        """
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: 'http://fake.com/no_trailing_slash'})

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        # Humorously enough, the _repo_url attribute named no_trailing_slash should now have a
        # trailing slash
        self.assertEqual(iso_sync_run._repo_url, 'http://fake.com/no_trailing_slash/')

    @patch('pulp_rpm.plugins.importers.iso.sync.HTTPThreadedDownloader.cancel',
           side_effect=HTTPThreadedDownloader.cancel, autospec=HTTPThreadedDownloader.cancel)
    def test_cancel_sync(self, cancel):
        """
        Test what happens if cancel_sync is called when there is no Bumper.
        """
        # This just passes since the downloader library does not support cancellation. This helps
        #  us get one
        # more line of coverage though!
        self.iso_sync_run.cancel_sync()

        # Assert that the cancel Mock was called
        cancel.assert_called_once_with(self.iso_sync_run.downloader)
        # The progress report's state should now be cancelled
        self.assertEqual(self.iso_sync_run.progress_report.state,
                         SyncProgressReport.STATE_CANCELLED)

    @patch('pulp_rpm.plugins.importers.iso.sync.logger')
    def test_download_failed_during_iso_download(self, logger):
        self.iso_sync_run.progress_report._state = SyncProgressReport.STATE_ISOS_IN_PROGRESS
        url = 'http://www.theonion.com/articles/american-airlines-us-airways-merge-to-form' \
              '-worlds,31302/'
        iso = models.ISO('test.txt', 217,
                         'a1552efee6f04012bc7e1f3e02c00c6177b08217cead958c47ec83cb8f97f835')
        report = DownloadReport(url, '/fake/destination', iso)
        report.error_msg = 'uh oh'

        self.iso_sync_run.download_failed(report)

        self.assertEqual(logger.error.call_count, 1)
        log_msg = logger.error.mock_calls[0][1][0]
        self.assertTrue('uh oh' in log_msg)

    @patch('pulp_rpm.plugins.importers.iso.sync.logger')
    def test_download_failed_during_manifest(self, logger):
        self.iso_sync_run.progress_report._state = SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        url = 'http://www.theonion.com/articles/' + \
              'american-airlines-us-airways-merge-to-form-worlds,31302/'
        report = DownloadReport(url, '/fake/destination')
        report.error_report = {'why': 'because'}
        report.error_msg = 'uh oh'

        self.iso_sync_run.download_failed(report)

        # The manifest_state should be failed
        self.assertEqual(self.iso_sync_run.progress_report._state,
                         SyncProgressReport.STATE_MANIFEST_FAILED)
        self.assertEqual(self.iso_sync_run.progress_report.error_message, report.error_report)
        self.assertEqual(logger.error.call_count, 1)
        log_msg = logger.error.mock_calls[0][1][0]
        self.assertTrue('uh oh' in log_msg)

    @patch('pulp_rpm.plugins.importers.iso.sync.ISOSyncRun.download_failed')
    def test_download_succeeded(self, download_failed):
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write(
                'Descartes walks into a bar and sits down, the bartender walks up to him and says '
                '"You, my '
                'man, look like you need a stiff drink." Descartes considers this, and shakes his '
                'head "No, '
                'I don\'t think-" and ceases to exist.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 217,
                         'a1552efee6f04012bc7e1f3e02c00c6177b08217cead958c47ec83cb8f97f835',
                         unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination, iso)

        # Simulate having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        self.iso_sync_run.progress_report._state = SyncProgressReport.STATE_ISOS_IN_PROGRESS

        self.iso_sync_run.download_succeeded(report)

        # The sync conduit should have been called to save the unit
        self.sync_conduit.save_unit.assert_any_call(unit)
        # The download should not fail
        self.assertEqual(download_failed.call_count, 0)

    @patch('pulp_rpm.plugins.importers.iso.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_honors_validate_units_set_false(self, download_failed):
        """
        We have a setting that makes download validation optional. This test ensures that
        download_succeeded()
        honors that setting.
        """
        # In this config, we will set validate_units to False, which should make our
        # "wrong_checksum" OK
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
               importer_constants.KEY_VALIDATE: False})

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        destination = os.path.join(self.temp_dir, 'test.iso')
        with open(destination, 'w') as test_iso:
            test_iso.write(
                'What happens when you combine a mosquito with a mountain climber? Nothing. You '
                'can\'t cross a vector with a scalar.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 114, 'wrong checksum', unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination, iso)

        # Let's fake having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        iso_sync_run.progress_report._state = SyncProgressReport.STATE_ISOS_IN_PROGRESS

        iso_sync_run.download_succeeded(report)

        # The sync conduit should have been called to save the unit
        self.sync_conduit.save_unit.assert_any_call(unit)
        # The download should not fail
        self.assertEqual(download_failed.call_count, 0)

    @patch('pulp_rpm.plugins.importers.iso.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_honors_validate_units_set_true(self, download_failed):
        """
        We have a setting that makes download validation optional. This test ensures that
        download_succeeded()
        honors that setting.
        """
        # In this config, we will set validate_units to False, which should make our
        # "wrong_checksum" OK
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
               importer_constants.KEY_VALIDATE: True})

        iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write('Boring test data.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 114, 'wrong checksum', unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination, iso)

        # Let's fake having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        iso_sync_run.progress_report._state = SyncProgressReport.STATE_ISOS_IN_PROGRESS

        iso_sync_run.download_succeeded(report)

        # Because we fail validation, the save_unit step will not be called
        self.assertEqual(self.sync_conduit.save_unit.call_count, 0)
        # The download should be marked failed
        self.assertEqual(download_failed.call_count, 1)
        download_failed.assert_called_once_with(report)

    @patch('pulp_rpm.plugins.importers.iso.sync.ISOSyncRun.download_failed')
    def test_download_succeeded_fails_checksum(self, download_failed):
        """
        This test verifies that download_succeeded does the right thing if the checksum fails. Note
        that we are also implicitly testing that the default behavior is to validate downloads by
        not setting it in this test. There are two other tests that verify that setting the boolean
        explicitly is honored.
        """
        self.config.override_config[importer_constants.KEY_VALIDATE] = True

        iso_sync_run = ISOSyncRun(self.sync_conduit, self.config)

        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write('Boring test data.')
        unit = MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 114, 'wrong checksum', unit)
        iso.url = 'http://fake.com'
        report = DownloadReport(iso.url, destination, iso)

        # Let's fake having downloaded the whole file
        iso.bytes_downloaded = iso.size
        report.bytes_downloaded = iso.size
        iso_sync_run.progress_report._state = SyncProgressReport.STATE_ISOS_IN_PROGRESS

        iso_sync_run.download_succeeded(report)

        # Because we fail validation, the save_unit step will not be called
        self.assertEqual(self.sync_conduit.save_unit.call_count, 0)
        # The download should be marked failed
        self.assertEqual(download_failed.call_count, 1)
        download_failed.assert_called_once_with(report)

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test_perform_sync(self, mock_download):
        """
        Assert that perform_sync() makes appropriate changes to the DB
        """
        mock_download.side_effect = self.fake_download

        report = self.iso_sync_run.perform_sync()

        # There should now be three Units in the DB, but only test3.iso is the new one
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {
            'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
            'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)

        # Check that no other units were associated with the repository
        self.assertEquals(0, self.sync_conduit.associate_existing.call_count)

        # The state should now be COMPLETE
        self.assertEqual(self.iso_sync_run.progress_report._state,
                         SyncProgressReport.STATE_COMPLETE)
        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is False
        # by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 0)

        self.assertEqual(report.summary['state'], ISOProgressReport.STATE_COMPLETE)

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test_perform_sync_available_local(self, mock_download):
        """
        Test that when content is already available within Pulp it is associated with the
        repository if necessary.
        """
        # Set up a sync where two of the units already exist in Pulp
        mock_download.side_effect = self.fake_download
        self.sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=self.pkg_dir,
                                                            existing_units=[],
                                                            pulp_units=self.existing_units)
        self.iso_sync_run = ISOSyncRun(self.sync_conduit, self.config)
        self.iso_sync_run.perform_sync()

        # Confirm the list of unit key dictionaries was given to associate_existing
        expected_units = [unit.unit_key for unit in self.existing_units
                          if unit.unit_key['name'] != 'test4.iso']
        self.sync_conduit.associate_existing.assert_called_once_with(models.ISO.TYPE,
                                                                     expected_units)
        self.assertEqual(1, self.sync_conduit.associate_existing.call_count)

        # test3.iso is in the manifest, but is not present locally, so we'd better download it.
        self.assertEqual(2, mock_download.call_count)
        expected_url = mock_download.call_args_list[0][0][0][0].url
        self.assertEqual('http://fake.com/iso_feed/PULP_MANIFEST', expected_url)
        expected_url = mock_download.call_args_list[1][0][0][0].url
        self.assertEqual('http://fake.com/iso_feed/test3.iso', expected_url)

    @patch('nectar.downloaders.local.LocalFileDownloader.download')
    def test_perform_local_sync(self, mock_download):
        """
        Assert that perform_sync() works equally well with a local feed
        """
        mock_download.side_effect = self.fake_download
        self.config.override_config[importer_constants.KEY_FEED] = 'file:///a/b/c'
        self.iso_sync_run = ISOSyncRun(self.sync_conduit, self.config)

        report = self.iso_sync_run.perform_sync()

        # There should now be three Units in the DB, but only test3.iso is the new one
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {
            'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
            'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)
        # The state should now be COMPLETE
        self.assertEqual(self.iso_sync_run.progress_report._state,
                         SyncProgressReport.STATE_COMPLETE)
        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is False
        # by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 0)

        self.assertEqual(report.summary['state'], ISOProgressReport.STATE_COMPLETE)

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test_perform_sync_malformed_pulp_manifest(self, download):
        """
        Assert the perform_sync correctly handles the situation when the PULP_MANIFEST file is not
        in the expected format.
        """

        def fake_download(request_list):
            for request in request_list:
                request.destination.write('This is not what a PULP_MANIFEST should look like.')

        download.side_effect = fake_download

        self.iso_sync_run.perform_sync()

        self.assertEquals(type(self.iso_sync_run.progress_report), SyncProgressReport)
        self.assertEqual(self.iso_sync_run.progress_report._state,
                         SyncProgressReport.STATE_MANIFEST_FAILED)
        self.assertEqual(self.iso_sync_run.progress_report.error_message,
                         'The PULP_MANIFEST file was not in the expected format.')

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test_perform_sync_manifest_io_error(self, download):
        """
        Assert the perform_sync correctly handles the situation when retrieving the PULP_MANIFEST
        file raises an IOError.
        """
        download.side_effect = IOError()

        self.iso_sync_run.perform_sync()

        self.assertEquals(type(self.iso_sync_run.progress_report), SyncProgressReport)

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test_perform_sync_remove_missing_units_set_false(self, mock_download):
        mock_download.side_effect = self.fake_download

        # Make sure the missing ISOs don't get removed if they aren't supposed to
        config = importer_mocks.get_basic_config(**{
            importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
            importer_constants.KEY_MAX_SPEED: 500.0,
            importer_constants.KEY_MAX_DOWNLOADS: 5,
            importer_constants.KEY_PROXY_HOST: 'proxy.com',
            importer_constants.KEY_PROXY_PORT: 1234,
            importer_constants.KEY_PROXY_USER: "the_dude",
            importer_constants.KEY_PROXY_PASS: 'bowling',
            importer_constants.KEY_UNITS_REMOVE_MISSING: False,
            importer_constants.KEY_SSL_CLIENT_CERT: "Trust me, I'm who I say I am.",
            importer_constants.KEY_SSL_CLIENT_KEY: "Secret Key",
            importer_constants.KEY_SSL_CA_CERT: "Uh, I guess that's the right server.",
            importer_constants.KEY_VALIDATE: False,
        })

        self.iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        self.iso_sync_run.perform_sync()

        # There should now be three Units in the DB
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {
            'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
            'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)
        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is
        # False by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 0)

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test_perform_sync_remove_missing_units_set_true(self, mock_download):
        mock_download.side_effect = self.fake_download

        # Make sure the missing ISOs get removed when they are supposed to
        config = importer_mocks.get_basic_config(**{
            importer_constants.KEY_FEED: 'http://fake.com/iso_feed/',
            importer_constants.KEY_MAX_SPEED: 500.0,
            importer_constants.KEY_MAX_DOWNLOADS: 5,
            importer_constants.KEY_PROXY_HOST: 'proxy.com',
            importer_constants.KEY_PROXY_PORT: 1234,
            importer_constants.KEY_PROXY_USER: "the_dude",
            importer_constants.KEY_PROXY_PASS: 'bowling',
            importer_constants.KEY_UNITS_REMOVE_MISSING: True,
            importer_constants.KEY_SSL_CLIENT_CERT: "Trust me, I'm who I say I am.",
            importer_constants.KEY_SSL_CLIENT_KEY: "Secret Key",
            importer_constants.KEY_SSL_CA_CERT: "Uh, I guess that's the right server.",
            importer_constants.KEY_VALIDATE: False,
        })

        self.iso_sync_run = ISOSyncRun(self.sync_conduit, config)

        repo = MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        repo.working_dir = working_dir

        self.iso_sync_run.perform_sync()

        # There should now be three Units in the DB
        units = [tuple(call)[1][0] for call in self.sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 1)
        expected_unit = {
            'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
            'size': 34, 'contents': 'Are you starting to get the idea?\n', 'name': 'test3.iso'}
        unit = units[0]
        self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
        self.assertEqual(unit.unit_key['size'], expected_unit['size'])
        expected_storage_path = os.path.join(
            self.pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
            str(unit.unit_key['size']), unit.unit_key['name'])
        self.assertEqual(unit.storage_path, expected_storage_path)

        # There should be 0 calls to sync_conduit.remove_unit, since remove_missing_units is
        # False by default
        self.assertEqual(self.sync_conduit.remove_unit.call_count, 1)
        removed_unit = self.sync_conduit.remove_unit.mock_calls[0][1][0]
        self.assertEqual(removed_unit.unit_key,
                         {'name': 'test4.iso', 'size': 4, 'checksum': 'sum4'})

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test__download_isos(self, mock_download):
        mock_download.side_effect = self.fake_download

        # We need to mark the iso_downloader as being in the ISO downloading state
        self.iso_sync_run.progress_report._state = SyncProgressReport.STATE_ISOS_IN_PROGRESS
        # Let's put three ISOs in the manifest
        manifest = StringIO()
        manifest.write(
            'test.iso,f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0,16\n')
        manifest.write(
            'test2.iso,c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16,22\n')
        manifest.write(
            'test3.iso,94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c,34')
        manifest.seek(0)
        manifest = models.ISOManifest(manifest, 'https://fake.com/')
        # Add expected test data to each ISO
        manifest._isos[0].expected_test_data = 'This is a file.\n'
        manifest._isos[1].expected_test_data = 'This is another file.\n'
        manifest._isos[2].expected_test_data = 'Are you starting to get the idea?\n'

        self.iso_sync_run._download_isos(manifest)

        # There should have been two calls to the sync_conduit per ISO, for a total of six calls.
        #  Once each to
        # initialize the unit, and once each to save it
        self.assertEqual(self.sync_conduit.init_unit.call_count, 3)
        self.assertEqual(self.sync_conduit.save_unit.call_count, 3)

        for index, iso in enumerate(manifest):
            expected_relative_path = os.path.join(iso.name, iso.checksum,
                                                  str(iso.size), iso.name)
            self.sync_conduit.init_unit.assert_any_call(
                TYPE_ID_ISO,
                {'name': iso.name, 'size': iso.size, 'checksum': iso.checksum},
                {server_constants.PULP_USER_METADATA_FIELDNAME: {}}, expected_relative_path)
            unit = self.sync_conduit.save_unit.call_args_list[index][0][0]
            self.assertEqual(unit.unit_key['name'], iso.name)
            self.assertEqual(unit.unit_key['checksum'], iso.checksum)
            self.assertEqual(unit.unit_key['size'], iso.size)

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test__download_manifest(self, mock_download):
        mock_download.side_effect = self.fake_download

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

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    @patch('pulp_rpm.plugins.importers.iso.sync.ISOSyncRun.download_succeeded',
           side_effect=ISOSyncRun.download_failed)
    def test__download_manifest_failed(self, download_succeeded, mock_download):
        """
        Make sure we handle the situation correctly when the manifest fails to download.
        """
        mock_download.side_effect = self.fake_download
        download_succeeded.side_effect = self.iso_sync_run.download_failed
        self.iso_sync_run.progress_report._state = SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        try:
            self.iso_sync_run._download_manifest()
            self.fail('This should have raised an IOError, but it did not.')
        except IOError, e:
            self.assertEqual(str(e), 'Could not retrieve http://fake.com/iso_feed/PULP_MANIFEST')

    @patch('nectar.downloaders.threaded.HTTPThreadedDownloader.download')
    def test__download_manifest_encounters_malformed_manifest(self, download):
        """
        Make sure that _download_manifest raises a ValueError if the PULP_MANIFEST isn't in the
        expected format.
        """

        def fake_download(request_list):
            for request in request_list:
                request.destination.write('This is not what a PULP_MANIFEST should look like.')

        download.side_effect = fake_download
        self.iso_sync_run.progress_report.state = SyncProgressReport.STATE_MANIFEST_IN_PROGRESS

        try:
            # This should raise a ValueError
            self.iso_sync_run._download_manifest()
            self.fail('A ValueError should have been raised by the previous line, but was not!')
        except ValueError:
            # Excellent, a ValueError was raised.
            self.assertEqual(self.iso_sync_run.progress_report._state,
                             SyncProgressReport.STATE_MANIFEST_FAILED)
            self.assertEqual(self.iso_sync_run.progress_report.error_message,
                             'The PULP_MANIFEST file was not in the expected format.')

    def test__filter_missing_isos(self):
        """
        Make sure this method returns the items from the manifest that weren't in the
        sync_conduit. By
        default, remove_missing_units is False, so we will also assert that the return value of
        this method
        doesn't suggest removing any ISOs.
        """
        # Let's put all three mammajammas in the manifest
        manifest = ['%s,%s,%s' % (iso.unit_key['name'], iso.unit_key['checksum'],
                                  iso.unit_key['size'])
                    for iso in self.existing_units if iso.unit_key['name'] != 'test4.iso']
        manifest = '\n'.join(manifest)
        manifest = StringIO(manifest)
        manifest = models.ISOManifest(manifest, 'http://test.com')

        filtered_isos = self.iso_sync_run._filter_missing_isos(manifest)
        local_missing_isos, local_available_isos, remote_missing_isos = filtered_isos

        # Only the third item from the manifest should be missing locally
        self.assertEqual(local_missing_isos, [iso for iso in manifest if iso.name == 'test3.iso'])
        # The remote repo doesn't have test4.iso, and so this method should tell us
        self.assertEqual(len(remote_missing_isos), 1)
        remote_missing_iso = remote_missing_isos[0]
        self.assertEqual(remote_missing_iso.unit_key,
                         {'name': 'test4.iso', 'size': 4, 'checksum': 'sum4'})

    def test__filter_missing_isos_available_isos(self):
        """
        Test that when there are units in Pulp that match those in the manifest, but that are
        not currently associated with the repository, they are returned by _filter_missing_isos
        as the second list in the 3-tuple.
        """
        # Let's put all three mammajammas in the manifest
        manifest = ['%s,%s,%s' % (iso.unit_key['name'], iso.unit_key['checksum'],
                                  iso.unit_key['size']) for iso in self.existing_units]
        manifest = '\n'.join(manifest)
        manifest = StringIO(manifest)
        manifest = models.ISOManifest(manifest, 'http://test.com')

        # Set up the sync conduit to return all three units as units in Pulp, but only the first
        # is associated with the repository
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=self.pkg_dir,
                                                       existing_units=[self.existing_units[0]],
                                                       pulp_units=self.existing_units)
        iso_sync_run = ISOSyncRun(sync_conduit, self.config)

        filtered_isos = iso_sync_run._filter_missing_isos(manifest)
        local_missing_isos, local_available_isos, remote_missing_isos = filtered_isos

        # Everything except the first unit should be in the list of local available isos
        self.assertEqual(0, len(local_missing_isos))
        self.assertEqual(2, len(local_available_isos))
        for expected, actual in zip(sorted(self.existing_units[1:]), sorted(local_available_isos)):
            self.assertEqual(expected, actual)
