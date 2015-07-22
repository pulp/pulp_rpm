import mock

from pulp_rpm.extensions.admin.iso import upload
from pulp_rpm.common import ids
from pulp_rpm.devel.client_base import PulpClientTests


class TestUploadISOCommand(PulpClientTests):
    """
    Test the UploadISOCommand class.
    """

    @mock.patch('pulp_rpm.extensions.admin.iso.upload.UploadCommand.__init__', autospec=True,
                side_effect=upload.UploadCommand.__init__)
    def test___init__(self, __init__):
        """
        Test the constructor.
        """
        fake_upload_manager = mock.MagicMock()

        upload_command = upload.UploadISOCommand(self.context, fake_upload_manager)

        __init__.assert_called_once_with(upload_command, self.context, fake_upload_manager,
                                         name=upload.NAME,
                                         description=upload.DESCRIPTION)

    def test_determine_type_id(self):
        """
        Assert that the determine_type_id() method always returns the ISO type.
        """
        self.assertEqual(upload.UploadISOCommand.determine_type_id('/path/doesnt/matter/'),
                         ids.TYPE_ID_ISO)
        self.assertEqual(upload.UploadISOCommand.
                         determine_type_id('/another/path/that/doesnt/matter/'),
                         ids.TYPE_ID_ISO)

    @mock.patch('pulp_rpm.common.file_utils.calculate_size', autospec=True)
    @mock.patch('pulp_rpm.common.file_utils.calculate_checksum', autospec=True)
    @mock.patch('__builtin__.open', autospec=True)
    def test_generate_unit_key_and_metadata(self, mock_open, mock_checksum, mock_size):
        """
        Assert that generate_unit_key_and_metadata gathers the correct metadata from a file.
        """
        mock_checksum.return_value = 'abc'
        mock_size.return_value = 6
        unit_key, metadata = upload.UploadISOCommand.generate_unit_key_and_metadata('/fake/path')

        self.assertEqual(unit_key, {'checksum': 'abc', 'name': 'path', 'size': 6})

        # ISOs don't have metadata
        self.assertEqual(metadata, {})
