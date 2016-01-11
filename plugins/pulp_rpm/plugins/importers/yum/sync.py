import contextlib
import functools
import logging
import os
import random
import re
import shutil
import tempfile
import traceback

from gettext import gettext as _
from cStringIO import StringIO
from urlparse import urljoin

from nectar.request import DownloadRequest

from pulp.common.plugins import importer_constants
from pulp.server.db.model import LazyCatalogEntry
from pulp.plugins.util import nectar_config as nectar_utils, verification
from pulp.server.exceptions import PulpCodedException
from pulp.server.managers.repo import _common as common_utils
from pulp.server.controllers import repository as repo_controller

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import existing, purge
from pulp_rpm.plugins.importers.yum.listener import RPMListener, DRPMListener
from pulp_rpm.plugins.importers.yum.parse.treeinfo import DistSync
from pulp_rpm.plugins.importers.yum.repomd import (
    alternate, group, metadata, nectar_factory, packages, presto, primary, updateinfo)
from pulp_rpm.plugins.importers.yum.report import ContentReport, DistributionReport
from pulp_rpm.plugins.importers.yum.utils import RepoURLModifier


_logger = logging.getLogger(__name__)


class CancelException(Exception):
    pass


class RepoSync(object):

    def __init__(self, repo, conduit, config):
        """
        :param repo: the repository to sync
        :type repo: pulp.server.db.model.Repository
        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config: plugin configuration
        :type config: pulp.plugins.config.PluginCallConfiguration
        """
        self.cancelled = False
        self.working_dir = common_utils.get_working_directory()
        self.content_report = ContentReport()
        self.distribution_report = DistributionReport()
        self.progress_report = {
            'metadata': {'state': 'NOT_STARTED'},
            'content': self.content_report,
            'distribution': self.distribution_report,
            'errata': {'state': 'NOT_STARTED'},
            'comps': {'state': 'NOT_STARTED'},
        }
        self.conduit = conduit
        self.set_progress()
        self.repo = repo
        self.config = config
        self.nectar_config = nectar_utils.importer_config_to_nectar_config(config.flatten())
        self.skip_repomd_steps = False
        self.current_revision = 0
        self.downloader = None
        self.tmp_dir = None

        url_modify_config = {}
        if config.get('query_auth_token'):
            url_modify_config['query_auth_token'] = config.get('query_auth_token')
            skip_config = self.config.get(constants.CONFIG_SKIP, [])

            for type_id in ids.QUERY_AUTH_TOKEN_UNSUPPORTED:
                if type_id not in skip_config:
                    skip_config.append(type_id)
            self.config.override_config[constants.CONFIG_SKIP] = skip_config
            _logger.info(
                _('The following unit types do not support query auth tokens and will be skipped:'
                  ' {skipped_types}').format(skipped_types=ids.QUERY_AUTH_TOKEN_UNSUPPORTED)
            )
        self._url_modify = RepoURLModifier(**url_modify_config)

    def set_progress(self):
        """
        A convenience method to perform this very repetitive task. This is also
        a convenient time to check if we've been cancelled, and if so, raise
        the proper exception.
        """
        self.conduit.set_progress(self.progress_report)
        if self.cancelled is True:
            raise CancelException

    @property
    def sync_feed(self):
        """
        :return:    a list of the URLs of the feeds we can sync
        :rtype:     list
        """
        repo_url = self.config.get(importer_constants.KEY_FEED)
        if repo_url:
            repo_url_slash = self._url_modify(repo_url, ensure_trailing_slash=True)
            self.tmp_dir = tempfile.mkdtemp(dir=self.working_dir)
            try:
                self.check_metadata(repo_url_slash)
                return [repo_url_slash]
            except PulpCodedException:
                # treat as mirrorlist
                return self._parse_as_mirrorlist(repo_url)
            finally:
                shutil.rmtree(self.tmp_dir, ignore_errors=True)
        return [repo_url]

    @property
    def download_deferred(self):
        """
        Test the download policy to determine if downloading is deferred.

        :return: True if deferred.
        :rtype: bool
        """
        policy = self.config.get(
            importer_constants.DOWNLOAD_POLICY,
            importer_constants.DOWNLOAD_IMMEDIATE)
        return policy != importer_constants.DOWNLOAD_IMMEDIATE

    def _parse_as_mirrorlist(self, feed):
        """
        Treats the provided feed as mirrorlist. Parses its content and extracts
        urls to sync.

        :param feed: feed that should be treated as mirrorlist
        :type:       str

        :return:    list the URLs received from the mirrorlist
        :rtype:     list
        """
        url_file = StringIO()
        downloader = nectar_factory.create_downloader(feed, self.nectar_config)
        request = DownloadRequest(feed, url_file)
        downloader.download_one(request)
        url_file.seek(0)
        url_parse = url_file.read().split('\n')
        repo_url = []
        # Due to the fact, that format of mirrorlist can be different, this regex
        # matches the cases when the url is not commented out and does not have any
        # punctuation characters in front.
        pattern = re.compile("(^|^[\w\s=]+\s)((http(s)?)://.*)")
        for line in url_parse:
            for match in re.finditer(pattern, line):
                repo_url.append(match.group(2))
        random.shuffle(repo_url)
        return repo_url

    @contextlib.contextmanager
    def update_state(self, state_dict, unit_type=None):
        """
        Manage the state of a step in the sync process. This sets the state to
        running and complete when appropriate, and optionally decides if the
        step should be skipped (if a unit_type is passed in). This reports
        progress before and after the step executes.

        This context manager yields a boolean value; if True, the step should
        be skipped.

        :param state_dict:  any dictionary containing a key "state" whose value
                            is the state of the current step.
        :type  state_dict:  dict
        :param unit_type:   optional unit type. If provided, and if the value
                            appears in the list of configured types to skip,
                            the state will be set to SKIPPED and the yielded
                            boolean will be True.
        :type  unit_type:   str
        """
        skip_config = self.config.get(constants.CONFIG_SKIP, [])
        skip = unit_type is not None and unit_type in skip_config

        if skip:
            state_dict[constants.PROGRESS_STATE_KEY] = constants.STATE_SKIPPED
        else:
            state_dict[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.set_progress()

        yield skip

        if state_dict[constants.PROGRESS_STATE_KEY] == constants.STATE_RUNNING:
            state_dict[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
        self.set_progress()

    def run(self):
        """
        Steps through the entire workflow of a repo sync.

        :return:    A SyncReport detailing how the sync went
        :rtype:     pulp.plugins.model.SyncReport
        """
        # Empty list could be returned in case _parse_as_mirrorlist()
        # was not able to find any valid url
        if not self.sync_feed:
            raise PulpCodedException(error_code=error_codes.RPM1004, reason='Not found')
        url_count = 0
        for url in self.sync_feed:
            # Verify that we have a feed url.
            # if there is no feed url, then we have nothing to sync
            if url is None:
                raise PulpCodedException(error_code=error_codes.RPM1005)
            # using this tmp dir ensures that cleanup leaves nothing behind, since
            # we delete below
            self.tmp_dir = tempfile.mkdtemp(dir=self.working_dir)
            url_count += 1
            try:
                with self.update_state(self.progress_report['metadata']):
                    metadata_files = self.check_metadata(url)
                    metadata_files = self.get_metadata(metadata_files)

                    # Save the default checksum from the metadata
                    self.save_default_metadata_checksum_on_repo(metadata_files)

                with self.update_state(self.content_report) as skip:
                    if not (skip or self.skip_repomd_steps):
                        self.update_content(metadata_files, url)

                _logger.info(_('Downloading additional units.'))

                with self.update_state(self.distribution_report,
                                       models.Distribution._content_type_id) as skip:
                    if not skip:
                        dist_sync = DistSync(self, url)
                        dist_sync.run()

                with self.update_state(self.progress_report['errata'], ids.TYPE_ID_ERRATA) as skip:
                    if not (skip or self.skip_repomd_steps):
                        self.get_errata(metadata_files)

                with self.update_state(self.progress_report['comps']) as skip:
                    if not (skip or self.skip_repomd_steps):
                        self.get_comps_file_units(metadata_files, group.process_group_element,
                                                  group.GROUP_TAG)
                        self.get_comps_file_units(metadata_files, group.process_category_element,
                                                  group.CATEGORY_TAG)
                        self.get_comps_file_units(metadata_files, group.process_environment_element,
                                                  group.ENVIRONMENT_TAG)

            except CancelException:
                report = self.conduit.build_cancel_report(self._progress_summary,
                                                          self.progress_report)
                report.canceled_flag = True
                return report

            except PulpCodedException, e:
                # Check if the caught exception indicates that the mirror is bad.
                # Try next mirror in the list without raising the exception.
                # In case it was the last mirror in the list, raise the exception.
                bad_mirror_exceptions = [error_codes.RPM1004, error_codes.RPM1006]
                if (e.error_code in bad_mirror_exceptions) and \
                        url_count != len(self.sync_feed):
                            continue
                else:
                    self._set_failed_state(e)
                    raise

            except Exception, e:
                # In case other exceptions were caught that are not related to the state of the
                # mirror, raise the exception immediately and do not iterate throught the rest
                # of the mirrors.
                _logger.exception(e)
                self._set_failed_state(e)
                report = self.conduit.build_failure_report(self._progress_summary,
                                                           self.progress_report)
                return report

            finally:
                # clean up whatever we may have left behind
                shutil.rmtree(self.tmp_dir, ignore_errors=True)

            self.save_repomd_revision()
            _logger.info(_('Sync complete.'))
            return self.conduit.build_success_report(self._progress_summary,
                                                     self.progress_report)

    def _set_failed_state(self, exception):
        """
        Sets failed state of the task and caught error in the progress status.

        :param exception: caught exception
        :type: Exception
        """
        for step, value in self.progress_report.iteritems():
            if value.get('state') == constants.STATE_RUNNING:
                value['state'] = constants.STATE_FAILED
                value['error'] = str(exception)
        self.set_progress()

    @property
    def _progress_summary(self):
        """
        Create a summary report from the detailed progress report that only
        includes the final state of each step.

        :return:    exactly like the progress report, but each step's dictionary
                    only includes the 'state' key with its final value.
        :type:      dict
        """
        ret = {}
        for step_name, progress_dict in self.progress_report.iteritems():
            ret[step_name] = {'state': progress_dict['state']}
        return ret

    def check_metadata(self, url):
        """
        :param url: curret URL we should sync
        :type url: str

        :return:    instance of MetadataFiles
        :rtype:     pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        _logger.info(_('Downloading metadata from %(feed)s.') % {'feed': url})
        metadata_files = metadata.MetadataFiles(url, self.tmp_dir, self.nectar_config,
                                                self._url_modify)
        try:
            metadata_files.download_repomd()
        except IOError, e:
            raise PulpCodedException(error_code=error_codes.RPM1004, reason=str(e))

        _logger.info(_('Parsing metadata.'))

        try:
            metadata_files.parse_repomd()
        except ValueError:
            _logger.debug(traceback.format_exc())
            raise PulpCodedException(error_code=error_codes.RPM1006)
        return metadata_files

    def get_metadata(self, metadata_files):
        """
        :param metadata_files: instance of MetadataFiles
        :type: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :return:    instance of MetadataFiles where each relevant file has been
                    identified and downloaded.
        :rtype:     pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """

        # allow the downloader to be accessed by the cancel method if necessary
        self.downloader = metadata_files.downloader
        scratchpad = self.conduit.get_scratchpad() or {}
        previous_revision = scratchpad.get(constants.REPOMD_REVISION_KEY, 0)
        previous_skip_set = set(scratchpad.get(constants.PREVIOUS_SKIP_LIST, []))
        current_skip_set = set(self.config.get(constants.CONFIG_SKIP, []))
        self.current_revision = metadata_files.revision
        # if the revision is positive, hasn't increased and the skip list doesn't include
        # new types that weren't present on the last run...
        if 0 < metadata_files.revision <= previous_revision \
                and previous_skip_set - current_skip_set == set():
            _logger.info(_('upstream repo metadata has not changed. Skipping steps.'))
            self.skip_repomd_steps = True
            return metadata_files
        else:
            _logger.info(_('Downloading metadata files.'))
            metadata_files.download_metadata_files()
            self.downloader = None
            _logger.info(_('Generating metadata databases.'))
            metadata_files.generate_dbs()
            self.import_unknown_metadata_files(metadata_files)
            return metadata_files

    def save_repomd_revision(self):
        """
        If there were no errors during the sync, save the repomd revision
        number to the scratchpad along with the configured skip list used
        by this run.
        """
        non_success_states = (constants.STATE_FAILED, constants.STATE_CANCELLED)
        if len(self.content_report['error_details']) == 0\
                and self.content_report[constants.PROGRESS_STATE_KEY] not in non_success_states:
            _logger.debug(_('saving repomd.xml revision number and skip list to scratchpad'))
            scratchpad = self.conduit.get_scratchpad() or {}
            scratchpad[constants.REPOMD_REVISION_KEY] = self.current_revision
            # we save the skip list so if one of the types contained in it gets removed, the next
            # sync will know to not skip based on repomd revision
            scratchpad[constants.PREVIOUS_SKIP_LIST] = self.config.get(
                constants.CONFIG_SKIP, [])
            self.conduit.set_scratchpad(scratchpad)

    def save_default_metadata_checksum_on_repo(self, metadata_files):
        """
        Determine the default checksum that should be used for metadata files and save it in
        the repo scratchpad.

        There is no good way to order a preference on the checksum type so the first one
        found is used.

        :param metadata_files:  object containing access to all metadata files
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        checksum_type = None
        for metadata_item in metadata_files.metadata.iteritems():
            if 'checksum' in metadata_item[1]:
                checksum_type = metadata_item[1]['checksum']['algorithm']
                break
        if checksum_type:
            checksum_type = verification.sanitize_checksum_type(checksum_type)
            scratchpad = self.conduit.get_repo_scratchpad()
            scratchpad[constants.SCRATCHPAD_DEFAULT_METADATA_CHECKSUM] = checksum_type
            self.conduit.set_repo_scratchpad(scratchpad)

    def import_unknown_metadata_files(self, metadata_files):
        """
        Import metadata files whose type is not known to us. These are any files
        that we are not already parsing.

        :param metadata_files:  object containing access to all metadata files
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        for metadata_type, file_info in metadata_files.metadata.iteritems():
            if metadata_type not in metadata_files.KNOWN_TYPES:
                file_path = file_info['local_path']
                checksum_type = file_info['checksum']['algorithm']
                checksum_type = verification.sanitize_checksum_type(checksum_type)
                checksum = file_info['checksum']['hex_digest']
                # Find an existing model
                model = models.YumMetadataFile.objects.filter(
                    data_type=metadata_type,
                    repo_id=self.repo.repo_id).first()
                # If an existing model, use that
                if model:
                    model.checksum = checksum
                    model.checksum_type = checksum_type
                else:
                    # Else, create a  new mode
                    model = models.YumMetadataFile(
                        data_type=metadata_type,
                        repo_id=self.repo.repo_id,
                        checksum=checksum,
                        checksum_type=checksum_type)

                model.set_storage_path(os.path.basename(file_path))
                model.save()
                model.import_content(file_path)

                # associate/re-associate model to the repo
                repo_controller.associate_single_unit(self.repo, model)

    def update_content(self, metadata_files, url):
        """
        Decides what to download and then downloads it

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param url: curret URL we should sync
        :type: str
        """
        rpms_to_download, drpms_to_download = self._decide_what_to_download(metadata_files)
        self.download_rpms(metadata_files, rpms_to_download, url)
        self.download_drpms(metadata_files, drpms_to_download, url)
        self.conduit.build_success_report({}, {})
        # removes unwanted units according to the config settings
        purge.purge_unwanted_units(metadata_files, self.conduit, self.config)

    def _decide_what_to_download(self, metadata_files):
        """
        Given the metadata files, decides which RPMs and DRPMs should be
        downloaded. Also sets initial values on the progress report for total
        number of things to download and the total size in bytes.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :return:    tuple of (set(RPM.NAMEDTUPLEs), set(DRPM.NAMEDTUPLEs))
        :rtype:     tuple
        """
        _logger.info(_('Determining which units need to be downloaded.'))
        rpms_to_download, rpms_count, rpms_total_size = \
            self._decide_rpms_to_download(metadata_files)
        drpms_to_download, drpms_count, drpms_total_size = \
            self._decide_drpms_to_download(metadata_files)

        unit_counts = {
            'rpm': rpms_count,
            'drpm': drpms_count,
        }
        total_size = sum((rpms_total_size, drpms_total_size))
        self.content_report.set_initial_values(unit_counts, total_size)
        self.set_progress()
        return rpms_to_download, drpms_to_download

    def _decide_rpms_to_download(self, metadata_files):
        """
        Decide which RPMs should be downloaded based on the repo metadata and on
        the importer config.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :return:    tuple of (set(RPM.NAMEDTUPLEs), number of RPMs, total size in bytes)
        :rtype:     tuple
        """
        if ids.TYPE_ID_RPM in self.config.get(constants.CONFIG_SKIP, []):
            _logger.debug('skipping RPM sync')
            return set(), 0, 0
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)
        try:
            # scan through all the metadata to decide which packages to download
            package_info_generator = packages.package_list_generator(
                primary_file_handle, primary.PACKAGE_TAG, primary.process_package_element)
            wanted = self._identify_wanted_versions(package_info_generator)
            # check for the units that are not in the repo, but exist on the server
            # and associate them to the repo
            to_download = existing.check_all_and_associate(
                wanted.iterkeys(), self.conduit, self.download_deferred)
            count = len(to_download)
            size = 0
            for unit in to_download:
                size += wanted[unit]
            return to_download, count, size
        finally:
            primary_file_handle.close()

    def _decide_drpms_to_download(self, metadata_files):
        """
        Decide which DRPMs should be downloaded based on the repo metadata and on
        the importer config.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :return:    tuple of (set(DRPM.NAMEDTUPLEs), number of DRPMs, total size in bytes)
        :rtype:     tuple
        """
        if ids.TYPE_ID_DRPM in self.config.get(constants.CONFIG_SKIP, []):
            _logger.debug('skipping DRPM sync')
            return set(), 0, 0

        to_download = set()
        count = 0
        size = 0

        # multiple options for deltainfo files depending on the distribution
        # so we have to go through all of them
        for metadata_file_name in presto.METADATA_FILE_NAMES:
            presto_file_handle = metadata_files.get_metadata_file_handle(metadata_file_name)
            if presto_file_handle:
                try:
                    package_info_generator = packages.package_list_generator(
                        presto_file_handle,
                        presto.PACKAGE_TAG,
                        presto.process_package_element)
                    wanted = self._identify_wanted_versions(package_info_generator)
                    # check for the units that are not in the repo, but exist on the server
                    # and associate them to the repo
                    to_download = existing.check_all_and_associate(
                        wanted.iterkeys(), self.conduit, self.download_deferred)
                    count += len(to_download)
                    for unit in to_download:
                        size += wanted[unit]
                finally:
                    presto_file_handle.close()

        return to_download, count, size

    def catalog_generator(self, base_url, units):
        """
        Provides a wrapper around the *units* generator.
        As the generator is iterated, the deferred downloading (lazy) catalog entry is added.

        :param base_url: The base download URL.
        :type base_url: str
        :param units: A generator of (rpm|drpm) units.
        :return: A generator of units.
        :rtype: generator
        """
        for unit in units:
            unit.set_storage_path(unit.filename)
            entry = LazyCatalogEntry()
            entry.path = unit.storage_path
            entry.importer_id = str(self.conduit.importer_object_id)
            entry.unit_id = unit.id
            entry.unit_type_id = unit.type_id
            entry.url = urljoin(base_url, unit.relativepath)
            entry.save_revision()
            yield unit

    def add_rpm_unit(self, metadata_files, unit):
        """
        Add the specified RPM unit.

        :param metadata_files: metadata files object.
        :type metadata_files: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param unit: A content unit.
        :type unit: pulp_rpm.plugins.db.models.RpmBase
        """
        metadata_files.add_repodata(unit)
        unit.set_storage_path(unit.filename)
        unit.save()
        repo_controller.associate_single_unit(self.conduit.repo, unit)
        self.progress_report['content'].success(unit)
        self.conduit.set_progress(self.progress_report)

    # added for clarity
    add_drpm_unit = add_rpm_unit

    def download_rpms(self, metadata_files, rpms_to_download, url):
        """
        Actually download the requested RPMs. This method iterates over
        the appropriate metadata file and downloads those items which are present
        in the corresponding set. It also checks for the RPMs which exist
        in other repositories before downloading them. If they are already downloaded,
        we skip the download and just associate them to the given repository.

        :param metadata_files:      populated instance of MetadataFiles
        :type  metadata_files:      pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param rpms_to_download:    set of RPM.NAMEDTUPLEs
        :type  rpms_to_download:    set
        :param url: current URL we should sync
        :type: str
        """
        event_listener = RPMListener(self, metadata_files)
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)

        try:
            package_model_generator = packages.package_list_generator(
                primary_file_handle,
                primary.PACKAGE_TAG,
                primary.process_package_element)

            units_to_download = self._filtered_unit_generator(package_model_generator,
                                                              rpms_to_download)

            # Wrapped in a generator that adds entries to
            # the deferred (Lazy) catalog.
            units_to_download = self.catalog_generator(url, units_to_download)

            if self.download_deferred:
                for unit in units_to_download:
                    unit.downloaded = False
                    self.add_rpm_unit(metadata_files, unit)
                return

            download_wrapper = alternate.Packages(
                url,
                self.nectar_config,
                units_to_download,
                self.tmp_dir,
                event_listener,
                self._url_modify)

            # allow the downloader to be accessed by the cancel method if necessary
            self.downloader = download_wrapper.downloader
            _logger.info(_('Downloading %(num)s RPMs.') % {'num': len(rpms_to_download)})
            download_wrapper.download_packages()
            self.downloader = None
        finally:
            primary_file_handle.close()

    def download_drpms(self, metadata_files, drpms_to_download, url):
        """
        Actually download the requested DRPMs. This method iterates over
        the appropriate metadata file and downloads those items which are present
        in the corresponding set. It also checks for the DRPMs which exist
        in other repositories before downloading them. If they are already downloaded,
        we skip the download and just associate them to the given repository.

        Multiple options for deltainfo files depending on the distribution
        so we have to go through all of them to get all the DRPMs

        :param metadata_files:      populated instance of MetadataFiles
        :type  metadata_files:      pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param drpms_to_download:   set of DRPM.NAMEDTUPLEs
        :type  drpms_to_download:   set
        :param url: current URL we should sync
        :type: str
        """
        event_listener = DRPMListener(self, metadata_files)

        for presto_file_name in presto.METADATA_FILE_NAMES:
            presto_file_handle = metadata_files.get_metadata_file_handle(presto_file_name)
            if presto_file_handle:
                try:
                    package_model_generator = packages.package_list_generator(
                        presto_file_handle,
                        presto.PACKAGE_TAG,
                        presto.process_package_element)

                    units_to_download = self._filtered_unit_generator(package_model_generator,
                                                                      drpms_to_download)

                    # Wrapped in a generator that adds entries to
                    # the deferred (Lazy) catalog.
                    units_to_download = self.catalog_generator(url, units_to_download)

                    if self.download_deferred:
                        for unit in units_to_download:
                            unit.downloaded = False
                            self.add_drpm_unit(metadata_files, unit)
                        continue

                    download_wrapper = packages.Packages(
                        url,
                        self.nectar_config,
                        units_to_download,
                        self.tmp_dir,
                        event_listener,
                        self._url_modify)

                    # allow the downloader to be accessed by the cancel method if necessary
                    self.downloader = download_wrapper.downloader
                    _logger.info(_('Downloading %(num)s DRPMs.') % {'num': len(drpms_to_download)})
                    download_wrapper.download_packages()
                    self.downloader = None
                finally:
                    presto_file_handle.close()

    def cancel(self):
        """
        Cancels the current sync. Looks for a "downloader" object and calls its
        "cancel" method, and then triggers a progress report.
        """
        self.cancelled = True
        for step, value in self.progress_report.iteritems():
            if value.get('state') == constants.STATE_RUNNING:
                value['state'] = constants.STATE_CANCELLED
        try:
            self.downloader.cancel()
        except AttributeError:
            # there might not be a downloader to cancel right now.
            _logger.debug('could not cancel downloader')
        try:
            self.set_progress()
        # this exception is only raised for the benefit of the run() method so
        # that it can discontinue execution of its workflow.
        except CancelException:
            pass

    def get_errata(self, metadata_files):
        """
        Given repo metadata files, decides which errata to get and gets them
        based on importer config settings.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        errata_file_handle = metadata_files.get_metadata_file_handle(updateinfo.METADATA_FILE_NAME)
        if not errata_file_handle:
            _logger.debug('updateinfo not found')
            return
        try:
            self.save_fileless_units(errata_file_handle, updateinfo.PACKAGE_TAG,
                                     updateinfo.process_package_element, additive_type=True)
        finally:
            errata_file_handle.close()

    def get_comps_file_units(self, metadata_files, processing_function, tag):
        """
        Given repo metadata files, decides which groups to get and gets them
        based on importer config settings.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :param processing_function:  method to use for generating the units
        :type  processing_function:  function

        :param tag:  the name of the xml tag containing each unit
        :type  tag:  str
        """
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
            _logger.debug('comps metadata not found')
            return

        try:
            process_func = functools.partial(processing_function, self.repo.repo_id)

            self.save_fileless_units(group_file_handle, tag, process_func, mutable_type=True)
        finally:
            group_file_handle.close()

    def save_fileless_units(self, file_handle, tag, process_func, mutable_type=False,
                            additive_type=False):
        """
        Generic method for saving units parsed from a repo metadata file where
        the units do not have files to store on disk. For example, groups.

        :param file_handle:     open file-like object containing metadata
        :type  file_handle:     file
        :param tag:             XML tag that identifies each unit
        :type  tag:             basestring
        :param process_func:    function that processes each unit and returns
                                a dict representing that unit's attribute names
                                and values. The function must take one parameter,
                                which is an ElementTree instance
        :type  process_func:    function
        :param mutable_type:    iff True, each unit will be saved regardless of
                                whether it already exists in the repo. this is
                                useful for units like group and category which
                                don't have a version, but could change
        :type  mutable_type:    bool
        :param additive_type:   iff True, units will be updated instead of
                                replaced. For example, if you wanted to save an
                                errata and concatenate its package list with an
                                existing errata, you'd set this. Note that mutable_type
                                and additive_type are mutually exclusive.
        :type  additive_type:   bool
        """

        if mutable_type and additive_type:
            raise PulpCodedException(message="The mutable_type and additive_type arguments for "
                                             "this method are mutually exclusive.")

        # iterate through the file and determine what we want to have
        package_info_generator = packages.package_list_generator(file_handle,
                                                                 tag,
                                                                 process_func)
        # if units aren't mutable, we don't need to attempt saving units that
        # we already have
        if not mutable_type and not additive_type:
            wanted = (model.unit_key_as_named_tuple for model in package_info_generator)
            # given what we want, filter out what we already have
            to_save = existing.check_repo(wanted)

            # rewind, iterate again through the file, and save what we need
            file_handle.seek(0)
            all_packages = packages.package_list_generator(file_handle,
                                                           tag,
                                                           process_func)
            package_info_generator = \
                (model for model in all_packages if model.unit_key_as_named_tuple in to_save)

        for model in package_info_generator:
            existing_unit = model.__class__.objects.filter(**model.unit_key).first()
            if not existing_unit:
                model.save()
            else:
                if additive_type:
                    model = self._concatenate_units(existing_unit, model)
                    model.save()
                else:
                    # make sure the associate_unit call gets the existing unit
                    model = existing_unit

            repo_controller.associate_single_unit(self.repo, model)

    def _concatenate_units(self, existing_unit, new_unit):
        """
        Perform unit concatenation.

        :param existing_unit: The unit that is already in the DB
        :type  existing_unit: pulp.plugins.model.Unit

        :param new_unit: The unit we are combining with the existing unit
        :type  new_unit: pulp.server.db.model.ContentUnit
        """
        if existing_unit._content_type_id != new_unit._content_type_id:
            raise PulpCodedException(message="Cannot concatenate two units of different types. "
                                             "Tried to concatenate %s with %s" %
                                             (existing_unit.type_id, new_unit.type_id))

        if existing_unit.unit_key != new_unit.unit_key:
            raise PulpCodedException(message="Concatenated units must have the same unit key. "
                                             "Tried to concatenate %s with %s" %
                                             (existing_unit.unit_key, new_unit.unit_key))

        if isinstance(existing_unit, models.Errata):
            # add in anything from new_unit that we don't already have. We key
            # package lists by name for this concatenation.
            existing_package_list_names = [p['name'] for p in existing_unit.pkglist]

            for possible_new_pkglist in new_unit.pkglist:
                if possible_new_pkglist['name'] not in existing_package_list_names:
                    existing_unit.pkglist += [possible_new_pkglist]
        else:
            raise PulpCodedException(message="Concatenation of unit type %s is not supported" %
                                             existing_unit.type_id)

        # return the unit now that we've possibly modified it.
        return existing_unit

    def finalize(self):
        """
        Perform any necessary cleanup.
        """
        self.nectar_config.finalize()

    def _identify_wanted_versions(self, package_info_generator):
        """
        Given an iterator of Package instances available for download, scan
        through the Packages to decide which should be downloaded. If
        package_info_generator is in fact a generator, this will not consume
        much memory.

        :param package_info_generator:  iterator of pulp_rpm.plugins.db.models.Package
                                        instances
        :return:    dict where keys are Packages as named tuples, and values
                    are the size of each package
        :rtype:     dict
        """
        # keys are a model's key string minus any version info
        # values are dicts where keys are serialized versions, and values are
        # a tuple of (model as named tuple, size in bytes)
        wanted = {}

        number_old_versions_to_keep = \
            self.config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
        for model in package_info_generator:
            versions = wanted.setdefault(model.key_string_without_version, {})
            serialized_version = model.complete_version_serialized
            size = model.size

            # if we are limited on the number of old versions we can have,
            if number_old_versions_to_keep is not None:
                number_to_keep = number_old_versions_to_keep + 1
                if len(versions) < number_to_keep:
                    versions[serialized_version] = (model.unit_key_as_named_tuple, size)
                else:
                    smallest_version = sorted(versions.keys(), reverse=True)[:number_to_keep][-1]
                    if serialized_version > smallest_version:
                        del versions[smallest_version]
                        versions[serialized_version] = (model.unit_key_as_named_tuple, size)
            else:
                versions[serialized_version] = (model.unit_key_as_named_tuple, size)
        ret = {}
        for units in wanted.itervalues():
            for unit, size in units.itervalues():
                ret[unit] = size

        return ret

    def _filtered_unit_generator(self, units, to_download=None):
        """
        Given an iterator of Package instances and a collection (preferably a
        set for performance reasons) of Packages as named tuples, this returns
        a generator of those Package instances with corresponding entries in the
        "to_download" collection.

        :param units:       iterator of pulp_rpm.plugins.db.models.Package instances
        :type  units:       iterator
        :param to_download: collection (preferably a set) of Packages as named
                            tuples that we want to download
        :type  to_download: set

        :return:    generator of pulp_rpm.plugins.db.models.Package instances that
                    should be downloaded
        :rtype:     generator
        """
        for unit in units:
            if to_download is None:
                # assume we want to download everything
                yield unit
            elif unit.unit_key_as_named_tuple in to_download:
                yield unit
