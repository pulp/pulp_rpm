import logging
from nectar.listener import DownloadEventListener, AggregatingEventListener
from pulp.common.plugins import importer_constants
from pulp.plugins.util import verification
from pulp.server import util

from pulp_rpm.common import constants
from pulp_rpm.plugins.importers.yum.parse import rpm as rpm_parse


_logger = logging.getLogger(__name__)


class DistFileListener(AggregatingEventListener):
    """
    :ivar sync: The active sync object.
    :type sync: pulp_rpm.plugins.importers.yum.parse.treeinfo.DistSync
    """

    def __init__(self, sync):
        """
        :param sync: The active sync object.
        :type sync: pulp_rpm.plugins.importers.yum.parse.treeinfo.DistSync
        """
        super(DistFileListener, self).__init__()
        self.sync = sync

    def download_succeeded(self, report):
        """

        :param report:
        :type  report: nectar.report.DownloadReport
        :return:
        """
        self._decrement()
        super(DistFileListener, self).download_succeeded(report)

    def download_failed(self, report):
        """

        :param report:
        :type  report: nectar.report.DownloadReport
        :return:
        """
        self._decrement()
        super(DistFileListener, self).download_failed(report)

    def _decrement(self):
        self.sync.progress_report['items_left'] -= 1
        self.sync.set_progress()


class PackageListener(DownloadEventListener):
    """
    Listener for package downloads.

    :ivar sync: An active sync object.
    :type sync: pulp_rpm.plugins.importers.yum.sync.RepoSync
    :ivar metadata_files: Repository metadata files.
    :type metadata_files: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    """

    def __init__(self, sync, metadata_files):
        """
        :param sync: An active sync object.
        :type sync: pulp_rpm.plugins.importers.yum.sync.RepoSync
        :param metadata_files: Repository metadata files.
        :type metadata_files: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        super(PackageListener, self).__init__()
        self.metadata_files = metadata_files
        self.sync = sync

    def download_succeeded(self, report):
        """
        The callback when a download succeeds.

        :param report: the report for the succeeded download.
        :type  report: nectar.report.DownloadReport
        """
        unit = report.data
        self._verify_size(unit, report)
        self._validate_checksumtype(unit)
        self._verify_checksum(unit, report)

    def download_failed(self, report):
        """
        The callback when a download fails.

        :param report: the report for the failed download.
        :type  report: nectar.report.DownloadReport
        """
        unit = report.data
        report.error_report['url'] = report.url
        self.sync.progress_report['content'].failure(unit, report.error_report)
        self.sync.set_progress()

    def _verify_size(self, unit, report):
        """
        Verifies the size of the given unit if the sync is configured to do so.
        If the verification fails, the error is noted in this instance's progress
        report and the error is re-raised.

        :param unit: domain model instance of the package that was downloaded
        :type  unit: pulp_rpm.plugins.db.models.RpmBase
        :param report: report handed to this listener by the downloader
        :type  report: nectar.report.DownloadReport

        :raises verification.VerificationException: if the size of the content is incorrect
        """

        if not self.sync.config.get(importer_constants.KEY_VALIDATE):
            return

        try:
            with open(report.destination) as fp:
                verification.verify_size(fp, unit.size)

        except verification.VerificationException, e:
            error_report = {
                constants.UNIT_KEY: unit.unit_key,
                constants.ERROR_CODE: constants.ERROR_SIZE_VERIFICATION,
                constants.ERROR_KEY_EXPECTED_SIZE: unit.size,
                constants.ERROR_KEY_ACTUAL_SIZE: e[0]
            }
            self.sync.progress_report['content'].failure(unit, error_report)
            raise

    def _verify_checksum(self, unit, report):
        """
        Verifies the checksum of the given unit if the sync is configured to do so.
        If the verification fails, the error is noted in this instance's progress
        report and the error is re-raised.

        :param unit: domain model instance of the package that was downloaded
        :type  unit: pulp_rpm.plugins.db.models.NonMetadataPackage
        :param report: report handed to this listener by the downloader
        :type  report: nectar.report.DownloadReport

        :raises verification.VerificationException: if the checksum of the content is incorrect
        """

        if not self.sync.config.get(importer_constants.KEY_VALIDATE):
            return

        with open(report.destination) as fp:
            sums = util.calculate_checksums(fp, [util.TYPE_MD5, util.TYPE_SHA1, util.TYPE_SHA256])

        if sums[unit.checksumtype] != unit.checksum:
            error_report = {
                constants.NAME: unit.name,
                constants.ERROR_CODE: constants.ERROR_CHECKSUM_VERIFICATION,
                constants.CHECKSUM_TYPE: unit.checksumtype,
                constants.ERROR_KEY_CHECKSUM_EXPECTED: unit.checksum,
                constants.ERROR_KEY_CHECKSUM_ACTUAL: sums[unit.checksumtype]
            }
            self.sync.progress_report['content'].failure(unit, error_report)
            # I don't know why the argument is the calculated sum, but that's the pre-existing
            # behavior in pulp.server.util.verify_checksum
            raise verification.VerificationException(sums[unit.checksumtype])
        else:
            # The unit will be saved later in the workflow, after the file is moved into place.
            unit.checksums.update(sums)

    def _validate_checksumtype(self, unit):
        """
        Validate that the checksum type is one that we support.

        :param unit: model instance of the package that was downloaded
        :type  unit: pulp_rpm.plugins.db.models.NonMetadataPackage

        :raises verification.VerificationException: if the checksum type is not supported
        """
        if unit.checksumtype not in util.CHECKSUM_FUNCTIONS:
            error_report = {
                constants.NAME: unit.name,
                constants.ERROR_CODE: constants.ERROR_CHECKSUM_TYPE_UNKNOWN,
                constants.CHECKSUM_TYPE: unit.checksumtype,
                constants.ACCEPTED_CHECKSUM_TYPES: util.CHECKSUM_FUNCTIONS.keys()
            }
            self.sync.progress_report['content'].failure(unit, error_report)
            raise util.InvalidChecksumType()


class RPMListener(PackageListener):
    """
    The RPM/SRPM/DRPM package download listener.
    """

    def download_succeeded(self, report):
        with util.deleting(report.destination):
            unit = report.data
            try:
                super(RPMListener, self).download_succeeded(report)
            except (verification.VerificationException, util.InvalidChecksumType):
                # verification failed, unit not added
                return

            # we need to read package header in order to extract signature info
            # unit is not added if header cannot be read
            headers = rpm_parse.package_headers(report.destination)
            unit['signing_key'] = rpm_parse.package_signature(headers)
            added_unit = self.sync.add_rpm_unit(self.metadata_files, unit)
            added_unit.safe_import_content(report.destination)
            if not added_unit.downloaded:
                added_unit.downloaded = True
                added_unit.save()
