import logging
import shutil

from nectar.listener import DownloadEventListener, AggregatingEventListener
from pulp.common.plugins import importer_constants
from pulp.plugins.util import verification

from pulp_rpm.common import constants
from pulp_rpm.plugins.db import models


_logger = logging.getLogger(__name__)


class DistroFileListener(AggregatingEventListener):
    def __init__(self, progress_report, progress_callback):
        super(DistroFileListener, self).__init__()
        self.progress_report = progress_report
        self.progress_callback = progress_callback

    def download_succeeded(self, report):
        """

        :param report:
        :type  report: nectar.report.DownloadReport
        :return:
        """
        self._decrement()
        super(DistroFileListener, self).download_succeeded(report)

    def download_failed(self, report):
        """

        :param report:
        :type  report: nectar.report.DownloadReport
        :return:
        """
        self._decrement()
        super(DistroFileListener, self).download_failed(report)

    def _decrement(self):
        self.progress_report['items_left'] -= 1
        self.progress_callback()


class ContentListener(DownloadEventListener):
    def __init__(self, sync_conduit, progress_report, sync_call_config, metadata_files):
        """
        :type sync_call_config: pulp.plugins.config.PluginCallConfig
        """
        super(ContentListener, self).__init__()
        self.sync_conduit = sync_conduit
        self.progress_report = progress_report
        self.sync_call_config = sync_call_config
        self.metadata_files = metadata_files

    def download_succeeded(self, report):
        """
        :param report:
        :type  report: nectar.report.DownloadReport
        :return:
        """
        model = report.data

        try:
            self._verify_size(model, report)
            self._verify_checksum(model, report)
        except verification.VerificationException:
            # The verify methods populates the error details of the progress report.
            # There is also no need to clean up the bad file as the sync will blow away
            # the temp directory after it finishes. Simply punch out so the good unit
            # handling below doesn't run.
            return
        except verification.InvalidChecksumType:
            return

        # these are the only types we store repo metadata snippets on in the DB
        if isinstance(model, (models.RPM, models.SRPM)):
            self.metadata_files.add_repodata(model)
        # init unit, which is idempotent
        unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, model.relative_path)
        # move to final location
        shutil.move(report.destination, unit.storage_path)
        # save unit
        self.sync_conduit.save_unit(unit)
        self.progress_report['content'].success(model)
        self.sync_conduit.set_progress(self.progress_report)

    def download_failed(self, report):
        """

        :param report:
        :type  report: nectar.report.DownloadReport
        :return:
        """
        model = report.data
        report.error_report['url'] = report.url
        self.progress_report['content'].failure(model, report.error_report)
        self.sync_conduit.set_progress(self.progress_report)

    def _verify_size(self, model, report):
        """
        Verifies the size of the given unit if the sync is configured to do so. If the verification
        fails, the error is noted in this instance's progress report and the error is re-raised.

        :param model: domain model instance of the package that was downloaded
        :type  model: pulp_rpm.plugins.db.models.RPM
        :param report: report handed to this listener by the downloader
        :type  report: nectar.report.DownloadReport

        :raises verification.VerificationException: if the size of the content is incorrect
        """

        if not self.sync_call_config.get(importer_constants.KEY_VALIDATE):
            return

        try:
            with open(report.destination) as dest_file:
                verification.verify_size(dest_file, model.metadata['size'])

        except verification.VerificationException, e:
            error_report = {
                constants.UNIT_KEY: model.unit_key,
                constants.ERROR_CODE: constants.ERROR_SIZE_VERIFICATION,
                constants.ERROR_KEY_EXPECTED_SIZE: model.metadata['size'],
                constants.ERROR_KEY_ACTUAL_SIZE: e[0]
            }
            self.progress_report['content'].failure(model, error_report)
            raise

    def _verify_checksum(self, model, report):
        """
        Verifies the checksum of the given unit if the sync is configured to do so. If the verification
        fails, the error is noted in this instance's progress report and the error is re-raised.

        :param model: domain model instance of the package that was downloaded
        :type  model: pulp_rpm.plugins.db.models.RPM
        :param report: report handed to this listener by the downloader
        :type  report: nectar.report.DownloadReport

        :raises verification.VerificationException: if the checksum of the content is incorrect
        """

        if not self.sync_call_config.get(importer_constants.KEY_VALIDATE):
            return

        try:
            with open(report.destination) as dest_file:
                verification.verify_checksum(dest_file, model.unit_key['checksumtype'],
                                             model.unit_key['checksum'])

        except verification.VerificationException, e:
            error_report = {
                constants.NAME: model.unit_key['name'],
                constants.ERROR_CODE: constants.ERROR_CHECKSUM_VERIFICATION,
                constants.CHECKSUM_TYPE: model.unit_key['checksumtype'],
                constants.ERROR_KEY_CHECKSUM_EXPECTED: model.unit_key['checksum'],
                constants.ERROR_KEY_CHECKSUM_ACTUAL: e[0]
            }
            self.progress_report['content'].failure(model, error_report)
            raise
        except verification.InvalidChecksumType, e:
            error_report = {
                constants.NAME: model.unit_key['name'],
                constants.ERROR_CODE: constants.ERROR_CHECKSUM_TYPE_UNKNOWN,
                constants.CHECKSUM_TYPE: model.unit_key['checksumtype'],
                constants.ACCEPTED_CHECKSUM_TYPES: verification.CHECKSUM_FUNCTIONS.keys()
            }
            self.progress_report['content'].failure(model, error_report)
            raise
