import os
import unittest

import mock
from pulp.plugins.util import verification

from pulp_rpm.plugins.importers.yum import listener


class TestContentListener(unittest.TestCase):

    def setUp(self):
        self.test_rpm_path = os.path.join(os.path.dirname(__file__), '../../../../data/walrus-5.21-1.noarch.rpm')
        self.sync_conduit = mock.MagicMock()
        self.progress_report = mock.MagicMock()
        self.sync_call_config = mock.MagicMock()
        self.metadata_files = mock.MagicMock()
        self.report = mock.MagicMock()

    @mock.patch('shutil.move', autospec=True)
    def test_download_successful(self, mock_move):
        self.sync_call_config.get.return_value = False
        content_listener = listener.ContentListener(self.sync_conduit, self.progress_report,
                                                    self.sync_call_config, self.metadata_files)
        content_listener.download_succeeded(self.report)
        self.progress_report['content'].success.assert_called_once_with(self.report.data)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp.plugins.util.verification.verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.move', autospec=True)
    def test_download_successful_with_validation(self, mock_move, mock_verify_size,
                                                 mock_verify_checksum, mock_open):
        self.sync_call_config.get.return_value = True
        content_listener = listener.ContentListener(self.sync_conduit, self.progress_report,
                                                    self.sync_call_config, self.metadata_files)
        content_listener.download_succeeded(self.report)

        self.progress_report['content'].success.assert_called_once_with(self.report.data)
        mock_verify_size.assert_called_once()
        mock_verify_checksum.assert_called_once()

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp.plugins.util.verification.verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.move', autospec=True)
    def test_download_successful_invalid_file_size(self, mock_move, mock_verify_size,
                                                 mock_verify_checksum, mock_open):
        self.sync_call_config.get.return_value = True

        mock_verify_size.side_effect = verification.VerificationException(22) #seed the size found
        content_listener = listener.ContentListener(self.sync_conduit, self.progress_report,
                                                    self.sync_call_config, self.metadata_files)

        content_listener.download_succeeded(self.report)

        mock_verify_size.assert_called_once()
        self.assertFalse(self.progress_report['content'].success.called)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp.plugins.util.verification.verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.move', autospec=True)
    def test_download_successful_invalid_checksum_type(self, mock_move, mock_verify_size,
                                                 mock_verify_checksum, mock_open):
        self.sync_call_config.get.return_value = True

        mock_verify_checksum.side_effect = verification.InvalidChecksumType()
        content_listener = listener.ContentListener(self.sync_conduit, self.progress_report,
                                                    self.sync_call_config, self.metadata_files)

        content_listener.download_succeeded(self.report)

        mock_verify_checksum.assert_called_once()
        self.assertFalse(self.progress_report['content'].success.called)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp.plugins.util.verification.verify_checksum')
    @mock.patch('pulp.plugins.util.verification.verify_size')
    @mock.patch('shutil.move', autospec=True)
    def test_download_successful_invalid_checksum_verification(self, mock_move, mock_verify_size,
                                                 mock_verify_checksum, mock_open):
        self.sync_call_config.get.return_value = True

        mock_verify_checksum.side_effect = verification.VerificationException('bad')
        content_listener = listener.ContentListener(self.sync_conduit, self.progress_report,
                                                    self.sync_call_config, self.metadata_files)

        content_listener.download_succeeded(self.report)

        mock_verify_checksum.assert_called_once()
        self.assertFalse(self.progress_report['content'].success.called)
