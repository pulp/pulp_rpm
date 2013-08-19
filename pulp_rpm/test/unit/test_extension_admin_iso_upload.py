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
import hashlib
import mock

from pulp_rpm.common import models
from pulp_rpm.extension.admin.iso import upload
import rpm_support_base


class TestUploadISOCommand(rpm_support_base.PulpClientTests):
    """
    Test the UploadISOCommand class.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.upload.UploadCommand.__init__', autospec=True,
                side_effect=upload.UploadCommand.__init__)
    def test___init__(self, __init__):
        """
        Test the constructor.
        """
        fake_upload_manager = mock.MagicMock()

        upload_command = upload.UploadISOCommand(self.context, fake_upload_manager)

        __init__.assert_called_once_with(upload_command, self.context, fake_upload_manager, name=upload.NAME,
                                         description=upload.DESCRIPTION)

    def test_determine_type_id(self):
        """
        Assert that the determine_type_id() method always returns the ISO type.
        """
        self.assertEqual(upload.UploadISOCommand.determine_type_id('/path/doesnt/matter/'), models.ISO.TYPE)
        self.assertEqual(upload.UploadISOCommand.determine_type_id('/another/path/that/doesnt/matter/'),
                                                                   models.ISO.TYPE)

    @mock.patch('__builtin__.open', autospec=True)
    def test_generate_unit_key_and_metadata(self, mock_open):
        """
        Assert that generate_unit_key_and_metadata gathers the correct metadata from a file.
        """
        open_context_manager = mock_open.return_value.__enter__.return_value
        fake_data = 'Here lies a fake ISO file. Rest in peace.'
        fake_file = StringIO(fake_data)
        # Let's set the context manager's read, tell, and seek functions to pass through to the underlying
        # StringIO.
        open_context_manager.read = fake_file.read
        open_context_manager.tell = fake_file.tell
        open_context_manager.seek = fake_file.seek

        unit_key, metadata = upload.UploadISOCommand.generate_unit_key_and_metadata('/fake/path')

        # Let's calculate the expected checksum
        hasher = hashlib.sha256()
        hasher.update(fake_data)
        expected_checksum = hasher.hexdigest()

        self.assertEqual(unit_key, {'checksum': expected_checksum, 'name': 'path', 'size': len(fake_data)})
        # ISOs don't have metadata
        self.assertEqual(metadata, {})
