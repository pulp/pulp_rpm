import os
import unittest

import mock
from nectar.report import DownloadReport
from pulp.plugins.util import verification
from pulp.server import util

from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.importers.yum import listener


class TestRPMListenerDownloadSucceeded(unittest.TestCase):
    def setUp(self):
        self.mock_sync = mock.MagicMock()
        # this causes validation to be skipped
        self.mock_sync.config.get.return_value = False
        self.mock_metadata_files = mock.MagicMock()
        self.listener = listener.RPMListener(self.mock_sync, self.mock_metadata_files)
        self.report = DownloadReport('http://pulpproject.org', '/a/b/c')

    @mock.patch('pulp.server.util.deleting')
    def test_calls_deleting(self, mock_deleting):
        unit = mock.MagicMock()
        self.report.data = unit

        self.listener.download_succeeded(self.report)

        # it was called correctly
        mock_deleting.assert_called_once_with('/a/b/c')
        # it was used as a context manager
        self.assertEqual(mock_deleting.return_value.__exit__.call_count, 1)

    def test_change_download_flag(self):
        unit = mock.MagicMock()
        unit.checksumtype = 'sha256'
        self.report.data = unit
        added_unit = mock.MagicMock()
        added_unit.downloaded = False
        self.mock_sync.add_rpm_unit.return_value = added_unit

        self.listener.download_succeeded(self.report)

        # test flag changed to True and save was called
        self.assertEqual(added_unit.downloaded, True)
        self.assertEqual(added_unit.save.call_count, 1)

    def test_save_not_called(self):
        unit = mock.MagicMock()
        self.report.data = unit
        added_unit = mock.MagicMock()
        added_unit.downloaded = True
        self.mock_sync.add_rpm_unit.return_value = added_unit

        self.listener.download_succeeded(self.report)

        # test flag is still set to True but save was not called
        self.assertEqual(added_unit.downloaded, True)
        self.assertEqual(added_unit.save.call_count, 0)


class TestPackageListener(unittest.TestCase):
    def setUp(self):
        self.test_rpm_path = os.path.join(os.path.dirname(__file__),
                                          '../../../../data/walrus-5.21-1.noarch.rpm')
        self.conduit = mock.MagicMock()
        self.progress_report = mock.MagicMock()
        self.config = mock.MagicMock()
        self.metadata_files = mock.MagicMock()
        self.report = mock.MagicMock()

    @skip_broken
    @mock.patch('pulp.server.controllers.repository.associate_single_unit')
    @mock.patch('shutil.copy', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.listener.purge.remove_unit_duplicate_nevra')
    def test_download_successful(self, mock_nevra, mock_copy, mock_assoc):
        self.config.get.return_value = False
        content_listener = listener.PackageListener(self, self.metadata_files)
        content_listener.download_succeeded(self.report)
        self.progress_report['content'].success.assert_called_once_with(self.report.data)
        mock_nevra.assert_called_once_with(self.conduit.init_unit().unit_key,
                                           self.conduit.init_unit().type_id,
                                           self.conduit.repo_id)

    @skip_broken
    @mock.patch('pulp.server.controllers.repository.associate_single_unit')
    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp.plugins.util.verification.verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('pulp_rpm.plugins.importers.yum.listener.purge.remove_unit_duplicate_nevra')
    @mock.patch('shutil.copy', autospec=True)
    def test_download_successful_with_validation(self, mock_copy, mock_nevra, mock_verify_size,
                                                 mock_verify_checksum, mock_open, mock_assoc):
        self.config.get.return_value = True
        content_listener = listener.PackageListener(self, self.metadata_files)
        content_listener.download_succeeded(self.report)

        self.progress_report['content'].success.assert_called_once_with(self.report.data)
        mock_verify_size.assert_called_once()
        mock_verify_checksum.assert_called_once()
        mock_nevra.assert_called_once_with(self.conduit.init_unit().unit_key,
                                           self.conduit.init_unit().type_id,
                                           self.conduit.repo_id)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp.plugins.util.verification.verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.copy', autospec=True)
    def test_download_successful_invalid_file_size(self, mock_copy, mock_verify_size,
                                                   mock_verify_checksum, mock_open):
        self.config.get.return_value = True

        mock_verify_size.side_effect = verification.VerificationException(22)  # seed the size found
        content_listener = listener.PackageListener(self, self.metadata_files)

        self.assertRaises(
            verification.VerificationException, content_listener.download_succeeded, self.report)

        mock_verify_size.assert_called_once()
        self.assertFalse(self.progress_report['content'].success.called)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.listener.PackageListener._verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.copy', autospec=True)
    def test_download_successful_invalid_checksum_type(self, mock_copy, mock_verify_size,
                                                       mock_verify_checksum, mock_open):
        self.config.get.return_value = True

        mock_verify_checksum.side_effect = util.InvalidChecksumType()
        content_listener = listener.PackageListener(self, self.metadata_files)

        self.assertRaises(
            util.InvalidChecksumType, content_listener.download_succeeded, self.report)

        mock_verify_checksum.assert_called_once()
        self.assertFalse(self.progress_report['content'].success.called)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.listener.PackageListener._verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.copy', autospec=True)
    def test_download_successful_invalid_checksum_verification(self, mock_copy, mock_verify_size,
                                                               mock_verify_checksum, mock_open):
        self.config.get.return_value = True

        mock_verify_checksum.side_effect = verification.VerificationException('bad')
        content_listener = listener.PackageListener(self, self.metadata_files)

        self.assertRaises(
            util.InvalidChecksumType, content_listener.download_succeeded, self.report)

        mock_verify_checksum.assert_called_once()
        self.assertFalse(self.progress_report['content'].success.called)
