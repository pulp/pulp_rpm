import logging

from nectar.listener import DownloadEventListener, AggregatingEventListener
from pulp.common.plugins import importer_constants
from pulp.plugins.util import verification
from pulp.server.controllers import repository as repo_controller

from pulp_rpm.common import constants
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import purge


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
        :param sync_conduit: sync conduit for the sync
        :type sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param progress_report: progress report to write into
        :type progress_report: dict
        :param sync_call_config: call config for the sync
        :type sync_call_config: pulp.plugins.config.PluginCallConfig
        :param metadata_files: metadata files object corresponding with the current sync
        :type metadata_files: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        super(ContentListener, self).__init__()
        self.sync_conduit = sync_conduit
        self.progress_report = progress_report
        self.sync_call_config = sync_call_config
        self.metadata_files = metadata_files

    def download_succeeded(self, report):
        """
        The callback when a download succeeds.

        :param report: the report for the succeeded download.
        :type  report: nectar.report.DownloadReport
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

        purge.remove_unit_duplicate_nevra(model, self.sync_conduit.repo)

        model.set_content(report.destination)
        model.save()

        repo_controller.associate_single_unit(self.sync_conduit.repo, model)

        # TODO consider that if an exception occurs before here maybe it shouldn't call success?
        self.progress_report['content'].success(model)
        self.sync_conduit.set_progress(self.progress_report)

    def download_failed(self, report):
        """
        The callback when a download fails.

        :param report: the report for the failed download.
        :type  report: nectar.report.DownloadReport
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
        :type  model: pulp_rpm.plugins.db.models.RpmBase
        :param report: report handed to this listener by the downloader
        :type  report: nectar.report.DownloadReport

        :raises verification.VerificationException: if the size of the content is incorrect
        """

        if not self.sync_call_config.get(importer_constants.KEY_VALIDATE):
            return

        try:
            with open(report.destination) as dest_file:
                verification.verify_size(dest_file, model.size)

        except verification.VerificationException, e:
            error_report = {
                constants.UNIT_KEY: model.unit_key,
                constants.ERROR_CODE: constants.ERROR_SIZE_VERIFICATION,
                constants.ERROR_KEY_EXPECTED_SIZE: model.size,
                constants.ERROR_KEY_ACTUAL_SIZE: e[0]
            }
            self.progress_report['content'].failure(model, error_report)
            raise

    def _verify_checksum(self, model, report):
        """
        Verifies the checksum of the given unit if the sync is configured to do so. If the
        verification
        fails, the error is noted in this instance's progress report and the error is re-raised.

        :param model: domain model instance of the package that was downloaded
        :type  model: pulp_rpm.plugins.db.models.RpmBase
        :param report: report handed to this listener by the downloader
        :type  report: nectar.report.DownloadReport

        :raises verification.VerificationException: if the checksum of the content is incorrect
        """

        if not self.sync_call_config.get(importer_constants.KEY_VALIDATE):
            return

        try:
            with open(report.destination) as dest_file:
                verification.verify_checksum(dest_file, model.checksumtype,
                                             model.checksum)

        except verification.VerificationException, e:
            error_report = {
                constants.NAME: model.name,
                constants.ERROR_CODE: constants.ERROR_CHECKSUM_VERIFICATION,
                constants.CHECKSUM_TYPE: model.checksumtype,
                constants.ERROR_KEY_CHECKSUM_EXPECTED: model.checksum,
                constants.ERROR_KEY_CHECKSUM_ACTUAL: e[0]
            }
            self.progress_report['content'].failure(model, error_report)
            raise
        except verification.InvalidChecksumType, e:
            error_report = {
                constants.NAME: model.name,
                constants.ERROR_CODE: constants.ERROR_CHECKSUM_TYPE_UNKNOWN,
                constants.CHECKSUM_TYPE: model.checksumtype,
                constants.ACCEPTED_CHECKSUM_TYPES: verification.CHECKSUM_FUNCTIONS.keys()
            }
            self.progress_report['content'].failure(model, error_report)
            raise
