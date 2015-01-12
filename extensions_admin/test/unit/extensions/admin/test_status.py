"""
Tests for the pulp_rpm.extensions.admin.status module.
"""
from pulp.plugins.util import verification
import mock

from pulp_rpm.common import constants
from pulp_rpm.devel import client_base
from pulp_rpm.extensions.admin import status
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import report


class RpmStatusRendererTests(client_base.PulpClientTests):
    """
    This class contains tests for the RpmStatusRenderer class.
    """

    def test_render_download_step_checksum_type_error(self):
        """
        Assert correct behavior from render_download_step() when the progress report contains errors
        about checksum type being unknown. This asserts coverage on code that caused #1099771.

        https://bugzilla.redhat.com/show_bug.cgi?id=1099771
        """
        self.prompt.render_failure_message = mock.MagicMock()
        content_report = report.ContentReport()
        model = models.RPM('name', 0, '1.0.1', '2', 'x86_64', 'non_existing_checksum', 'checksum',
                           {'size': 1024})
        error_report = {
            constants.NAME: model.unit_key['name'],
            constants.ERROR_CODE: constants.ERROR_CHECKSUM_TYPE_UNKNOWN,
            constants.CHECKSUM_TYPE: model.unit_key['checksumtype'],
            constants.ACCEPTED_CHECKSUM_TYPES: verification.CHECKSUM_FUNCTIONS.keys()}
        content_report.failure(model, error_report)
        content_report['state'] = constants.STATE_COMPLETE
        progress_report = {'yum_importer': {'content': content_report}}
        renderer = status.RpmStatusRenderer(self.context)

        renderer.render_download_step(progress_report)

        # The call above should not have failed, and the error messages asserted below should have
        # been printed for the user.
        self.assertTrue('package errors encountered' in
                        self.prompt.render_failure_message.mock_calls[0][1][0])
        self.assertTrue('invalid checksum type (non_existing_checksum)' in
                        self.prompt.render_failure_message.mock_calls[1][1][0])

    def test_render_distribution_sync_step_with_error(self):
        """
        Assert that the expected messages are passed to render_failure_message in the event of a
        failed state.
        """
        self.prompt.render_failure_message = mock.MagicMock()
        error1 = ('mock_filename', {'error_message': 'mock_message', 'error_code': 'mock_code'})

        progress_report = {'yum_importer': {
            'distribution': {'state': constants.STATE_FAILED, 'error_details': [error1]}
        }}

        renderer = status.RpmStatusRenderer(self.context)

        renderer.render_distribution_sync_step(progress_report)
        expected_message = 'File: mock_filename\n'\
                           'Error Code:   mock_code\n'\
                           'Error Message: mock_message'

        self.prompt.render_failure_message.assert_has_calls(mock.call(expected_message))

    def test_render_distribution_sync_step_with_errors_with_missing_information(self):
        """
        Covers bugfix 1147078, tests that errors that do not have an error message or error code
        do not crash the sync.
        """
        self.prompt.render_failure_message = mock.MagicMock()

        # Incomplete error raised a KeyError
        error1 = ('mock_filename', {})

        progress_report = {'yum_importer': {
            'distribution': {'state': constants.STATE_FAILED, 'error_details': [error1]}
        }}

        renderer = status.RpmStatusRenderer(self.context)

        renderer.render_distribution_sync_step(progress_report)
        expected_message = 'File: mock_filename\n'\
                           'Error Code:   None\n'\
                           'Error Message: None'

        self.prompt.render_failure_message.assert_has_calls(mock.call(expected_message))

