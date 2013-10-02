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

import os
import unittest
import mock

from pulp_rpm.plugins.importers.yum import listener
from pulp.plugins.util import verification

"""
import pulp.server.managers.factory as manager_factory
manager_factory.initialize()

:param sync_conduit: provides access to relevant Pulp functionality
        :type  sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit

        :param call_config: plugin configuration
        :type  call_config: pulp.plugins.config.PluginCallConfiguration
"""

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
        self.progress_report['content'].success.assert_called_once()


#from pulp.plugins.util import verification
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

        self.progress_report['content'].success.assert_called_once()
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
        self.assertEquals(0, self.progress_report['content'].success.called)

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
        self.assertEquals(0, self.progress_report['content'].success.called)

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
        self.assertEquals(0, self.progress_report['content'].success.called)
