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
