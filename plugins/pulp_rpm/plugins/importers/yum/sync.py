import contextlib
import functools
import logging
import os
import random
import re
import shutil
import tempfile
import traceback

from collections import namedtuple
from gettext import gettext as _
from cStringIO import StringIO
from urlparse import urljoin

from mongoengine import NotUniqueError
from nectar.request import DownloadRequest

from pulp.common.plugins import importer_constants
from pulp.plugins.util import nectar_config as nectar_utils
from pulp.server import util
from pulp.server.controllers import repository as repo_controller
from pulp.server.db.model import LazyCatalogEntry
from pulp.server.exceptions import PulpCodedException
from pulp.server.managers.repo import _common as common_utils

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.controllers import errata as errata_controller
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import existing, purge
from pulp_rpm.plugins.importers.yum.listener import RPMListener
from pulp_rpm.plugins.importers.yum.parse import rpm as rpm_parse
from pulp_rpm.plugins.importers.yum.parse.treeinfo import DistSync
from pulp_rpm.plugins.importers.yum.repomd import (
    alternate, group, metadata, nectar_factory, packages, presto, primary, updateinfo)
from pulp_rpm.plugins.importers.yum.report import ContentReport, DistributionReport
from pulp_rpm.plugins.importers.yum.utils import RepoURLModifier


_logger = logging.getLogger(__name__)


# Data about wanted units.
# size - The size in bytes for the associated file.
# download_path - The relative path within the upstream YUM repository
#                 used to construct the download URL.
WantedUnitInfo = namedtuple('WantedUnitInfo', ('size', 'download_path'))


class RepoSync(object):
    """
    :ivar skip_repomd_steps:    if True, all parts of the sync that depend on yum repo metadata
                                will be skipped.
    :type skip_repomd_steps:    bool
    :ivar metadata_found:       if True, at least one type of repo metadata was found: either
                                yum metadata, or a treeinfo file
    :type metadata_found:       bool
    :ivar repomd_not_found_reason:  The reason to show the user why the yum repo metadata could
                                    not be found.
    :type repomd_not_found_reason:  basestring
    """

    def __init__(self, repo, conduit, config):
        """
        :param repo: the repository to sync
        :type repo: pulp.server.db.model.Repository
        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config: plugin configuration
        :type config: pulp.plugins.config.PluginCallConfiguration
        """
        self.working_dir = common_utils.get_working_directory()
        self.content_report = ContentReport()
        self.distribution_report = DistributionReport()
        self.progress_report = {
            'metadata': {'state': 'NOT_STARTED'},
            'content': self.content_report,
            'distribution': self.distribution_report,
            'errata': {'state': 'NOT_STARTED'},
            'comps': {'state': 'NOT_STARTED'},
            'purge_duplicates': {'state': 'NOT_STARTED'},
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
        # Was any repo metadata found? Includes either yum metadata or a treeinfo file. If this is
        # False at the end of the sync, then an error will be presented to the user.
        self.metadata_found = False
        # Store the reason that yum repo metadata was not found. In case a treeinfo file is also
        # not found, this error will be the one presented to the user. That preserves pre-existing
        # behavior that is yum-centric.
        self.repomd_not_found_reason = ''

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
        A convenience method to perform this very repetitive task.
        """
        self.conduit.set_progress(self.progress_report)

    @property
    def sync_feed(self):
        """
        :return:    a list of the URLs of the feeds we can sync
        :rtype:     list
        """
        repo_url = self.config.get(importer_constants.KEY_FEED)
        if repo_url:
            repo_url = self._url_modify(repo_url, ensure_trailing_slash=True)
            self.tmp_dir = tempfile.mkdtemp(dir=self.working_dir)

            # Try getting and parsing repomd.xml. If it works, return the URL.
            try:
                # it returns None if it can't download repomd.xml
                if self.check_metadata(repo_url):
                    return [repo_url]
            except PulpCodedException:
                # Fedora's mirror service has an unexpected behavior that even with a malformed path
                # such as this:
                # http://mirrors.fedoraproject.org/mirrorlist/BAD/DATA?repo=fedora-24&arch=x86_64
                # it will return the mirrorlist as if the path was just /mirrorlist/. That means
                # we won't get a Not Found error, but instead a parsing error, which shows up as
                # a PulpCodedException.
                pass

            # Try treating it as a mirrorlist.
            urls = self._parse_as_mirrorlist(repo_url)
            if urls:
                # set flag to True so when we would iterate through list of urls
                # we would not skip repomd steps
                self.skip_repomd_steps = False
                return urls

            # It's not a mirrorlist either, so skip all repomd steps.
            self.skip_repomd_steps = True
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
            is_last_mirror = url_count == len(self.sync_feed)
            try:
                with self.update_state(self.progress_report['metadata']):
                    metadata_files = self.check_metadata(url)
                    if not self.skip_repomd_steps:
                        metadata_files = self.get_metadata(metadata_files)

                        # Save the default checksum from the metadata
                        self.save_default_metadata_checksum_on_repo(metadata_files)

                with self.update_state(self.content_report) as skip:
                    if not (skip or self.skip_repomd_steps):
                        self.update_content(metadata_files, url)

                _logger.info(_('Downloading additional units.'))

                with self.update_state(self.distribution_report,
                                       ids.TYPE_ID_DISTRO) as skip:
                    if not skip:
                        dist_sync = DistSync(self, url)
                        dist_sync.run()
                        self.metadata_found |= dist_sync.metadata_found

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
                        self.get_comps_file_units(metadata_files, group.process_langpacks_element,
                                                  group.LANGPACKS_TAG)

                with self.update_state(self.progress_report['purge_duplicates']) as skip:
                    if not (skip or self.skip_repomd_steps):
                        purge.remove_repo_duplicate_nevra(self.conduit.repo_id)

                # skip to the next URL in case:
                #  - metadata was not found
                #  - it was not possible to sync distribution that does not have yum repo metadata
                #  - it was not the last mirror in the list
                if not self.metadata_found and not is_last_mirror:
                    continue

            except PulpCodedException, e:
                # Check if the caught exception indicates that the mirror is bad.
                # Try next mirror in the list without raising the exception.
                # In case it was the last mirror in the list, raise the exception.
                bad_mirror_exceptions = [error_codes.RPM1004, error_codes.RPM1006]
                if (e.error_code in bad_mirror_exceptions) and not is_last_mirror:
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

            if not self.metadata_found:
                # could not find yum repo metadata or a treeinfo file
                raise PulpCodedException(error_code=error_codes.RPM1004,
                                         reason=self.repomd_not_found_reason)

            if self.config.override_config.get(importer_constants.KEY_FEED):
                self.erase_repomd_revision()
            else:
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
        Download and parse repomd.xml

        If the download fails, sets the "skip_repomd_steps" attribute to True and populates the
        "repomd_not_found_reason" attribute.

        :param url: curret URL we should sync
        :type url: str

        :return:    instance of MetadataFiles
        :rtype:     pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :raises PulpCodedException: if the metadata cannot be parsed
        """
        _logger.info(_('Downloading metadata from %(feed)s.') % {'feed': url})
        metadata_files = metadata.MetadataFiles(url, self.tmp_dir, self.nectar_config,
                                                self._url_modify)
        try:
            metadata_files.download_repomd()
        except IOError as e:
            # remember the reason so it can be reported to the user if no treeinfo is found either.
            self.repomd_not_found_reason = e.message
            _logger.debug(_('No yum repo metadata found.'))
            # set flag to True in order to skip repomd steps, since metadata was not found
            self.skip_repomd_steps = True
            return

        self.skip_repomd_steps = False
        self.metadata_found = True
        _logger.info(_('Parsing metadata.'))

        try:
            metadata_files.parse_repomd()
        except ValueError:
            _logger.debug(traceback.format_exc())
            raise PulpCodedException(error_code=error_codes.RPM1006)
        return metadata_files

    def get_metadata(self, metadata_files):
        """
        Get metadata and decide whether to sync the repository or not.

        :param metadata_files: instance of MetadataFiles
        :type: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles

        :return:    instance of MetadataFiles where each relevant file has been
                    identified and downloaded.
        :rtype:     pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        self.downloader = metadata_files.downloader
        scratchpad = self.conduit.get_scratchpad() or {}
        previous_revision = scratchpad.get(constants.REPOMD_REVISION_KEY, 0)
        self.current_revision = metadata_files.revision
        # determine missing units
        missing_units = repo_controller.missing_unit_count(self.repo.repo_id)

        force_full_sync = repo_controller.check_perform_full_sync(self.repo.repo_id,
                                                                  self.conduit,
                                                                  self.config)

        # if the platform does not prescribe forcing a full sync
        # (due to removed unit, force_full flag, config change, etc.)
        # the current MD revision is not newer than the old one
        # and there are no missing units, or we have deferred download enabled
        # then skip fetching the repo MD :)
        skip_sync_steps = not force_full_sync and \
            0 < self.current_revision <= previous_revision and \
            (self.download_deferred or not missing_units)

        if skip_sync_steps:
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
            self.conduit.set_scratchpad(scratchpad)

    def erase_repomd_revision(self):
        """
        If we are syncing from a one-off URL, we should clobber the old repomd revision.
        """
        _logger.debug(_('erasing repomd.xml revision number and skip list from scratchpad'))
        scratchpad = self.conduit.get_scratchpad()
        if scratchpad:
            scratchpad[constants.REPOMD_REVISION_KEY] = None
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
            checksum_type = util.sanitize_checksum_type(checksum_type)
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
                checksum_type = util.sanitize_checksum_type(checksum_type)
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
                model.save_and_import_content(file_path)

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
        catalog = PackageCatalog(self.conduit.importer_object_id, url)
        rpms_to_download, drpms_to_download = self._decide_what_to_download(metadata_files, catalog)
        self.download_rpms(metadata_files, rpms_to_download, url)
        self.download_drpms(metadata_files, drpms_to_download, url)
        failed_signature_check = 0
        new_report = []
        for error in self.progress_report['content']['error_details']:
            # Nectar doesn't return error reports in the same format as other parts of the code
            # Use getattr() here to avoid KeyErrors
            if getattr(error, constants.ERROR_CODE, None) == constants.ERROR_KEY_ID_FILTER:
                failed_signature_check += 1
            else:
                new_report.append(error)
        if failed_signature_check:
            d = {constants.ERROR_CODE: constants.ERROR_INVALID_PACKAGE_SIG,
                 'count': '%s' % failed_signature_check}
            new_report.append(d)
            self.progress_report['content']['error_details'] = new_report
            _logger.warning(_('%s packages failed signature filter and were not imported.'
                            % failed_signature_check))
        self.conduit.build_success_report({}, {})
        # removes unwanted units according to the config settings
        purge.purge_unwanted_units(metadata_files, self.conduit, self.config, catalog)

    def _decide_what_to_download(self, metadata_files, catalog):
        """
        Given the metadata files, decides which RPMs and DRPMs should be
        downloaded. Also sets initial values on the progress report for total
        number of things to download and the total size in bytes.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param catalog:         Deferred downloading catalog.
        :type  catalog:         PackageCatalog

        :return:    tuple of (set(RPM.NAMEDTUPLEs), set(DRPM.NAMEDTUPLEs))
        :rtype:     tuple
        """
        _logger.info(_('Determining which units need to be downloaded.'))
        rpms_to_download, rpms_count, rpms_total_size = \
            self._decide_rpms_to_download(metadata_files, catalog)
        drpms_to_download, drpms_count, drpms_total_size = \
            self._decide_drpms_to_download(metadata_files, catalog)

        unit_counts = {
            'rpm': rpms_count,
            'drpm': drpms_count,
        }
        total_size = sum((rpms_total_size, drpms_total_size))
        self.content_report.set_initial_values(unit_counts, total_size)
        self.set_progress()
        return rpms_to_download, drpms_to_download

    def _decide_rpms_to_download(self, metadata_files, catalog):
        """
        Decide which RPMs should be downloaded based on the repo metadata and on
        the importer config.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param catalog:         Deferred downloading catalog.
        :type  catalog:         PackageCatalog

        :return:    tuple of (set(RPM.NAMEDTUPLEs), number of RPMs, total size in bytes)
        :rtype:     tuple

        :raises PulpCodedException: if there is some inconsistency in metadata
        """
        if ids.TYPE_ID_RPM in self.config.get(constants.CONFIG_SKIP, []):
            _logger.debug('skipping RPM sync')
            return set(), 0, 0
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)
        try:
            # scan through all the metadata to decide which packages to download
            package_info_generator = packages.package_list_generator(
                primary_file_handle, primary.PACKAGE_TAG, primary.process_package_element)

            wanted, primary_rpm_count = self._identify_wanted_versions(package_info_generator)
            if primary_rpm_count != metadata_files.rpm_count:
                reason = 'metadata is missing for some packages in filelists.xml and in other.xml'
                raise PulpCodedException(error_code=error_codes.RPM1015, reason=reason)

            # check for the units that are not in the repo, but exist on the server
            # and associate them to the repo
            to_download = existing.check_all_and_associate(
                wanted, self.conduit, self.config, self.download_deferred, catalog)
            count = len(to_download)
            size = 0
            for unit in to_download:
                size += wanted[unit].size
            return to_download, count, size
        finally:
            primary_file_handle.close()

    def _decide_drpms_to_download(self, metadata_files, catalog):
        """
        Decide which DRPMs should be downloaded based on the repo metadata and on
        the importer config.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param catalog:         Deferred downloading catalog.
        :type  catalog:         PackageCatalog

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
                    wanted, _ = self._identify_wanted_versions(package_info_generator)
                    # check for the units that are not in the repo, but exist on the server
                    # and associate them to the repo
                    to_download = existing.check_all_and_associate(
                        wanted, self.conduit, self.config, self.download_deferred, catalog)
                    count += len(to_download)
                    for unit in to_download:
                        size += wanted[unit].size
                finally:
                    presto_file_handle.close()

        return to_download, count, size

    def add_rpm_unit(self, metadata_files, unit):
        """
        Add the specified RPM, SRPM or DRPM unit.

        :param metadata_files: metadata files object.
        :type metadata_files: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param unit: A content unit.
        :type unit: pulp_rpm.plugins.db.models.RpmBase

        :return:    A content unit
        :rtype:     pulp_rpm.plugins.db.models.RpmBase
        """
        if isinstance(unit, (models.RPM, models.SRPM)):
            metadata_files.add_repodata(unit)
        unit.set_storage_path(unit.filename)
        try:
            unit.save()
        except NotUniqueError:
            unit = unit.__class__.objects.filter(**unit.unit_key).first()

        return unit

    def signature_filter_passed(self, unit):
        """
        Decide whether to associate unit or not based on its signature.

        :param unit: A content unit.
        :type unit: pulp_rpm.plugins.db.models.RpmBase

        :rtype: bool
        :return: True if unit passes the signature filter and has to be associated
        """
        if rpm_parse.signature_enabled(self.config):
            try:
                rpm_parse.filter_signature(unit, self.config)
            except PulpCodedException as e:
                _logger.debug(e)
                error_report = {
                    constants.NAME: unit.filename,
                    constants.ERROR_CODE: constants.ERROR_KEY_ID_FILTER,
                }

                self.progress_report['content'].failure(unit, error_report)
                self.conduit.set_progress(self.progress_report)
                return False

        return True

    def associate_rpm_unit(self, unit):
        """
        Associate unit with a repo and report this unit as a successfully synced one.
        It should be a last step in the sync of one unit.

        :param unit: A content unit
        :type  unit: pulp_rpm.plugins.db.models.RpmBase
        """
        repo_controller.associate_single_unit(self.conduit.repo, unit)
        self.progress_report['content'].success(unit)
        self.conduit.set_progress(self.progress_report)

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

            if self.download_deferred:
                catalog = PackageCatalog(self.conduit.importer_object_id, url)
                for unit in units_to_download:
                    unit.downloaded = False
                    unit = self.add_rpm_unit(metadata_files, unit)
                    self.associate_rpm_unit(unit)
                    catalog.add(unit, unit.download_path)
                return

            download_wrapper = alternate.Packages(
                url,
                self.nectar_config,
                units_to_download,
                self.tmp_dir,
                event_listener,
                self._url_modify)

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
        event_listener = RPMListener(self, metadata_files)

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

                    if self.download_deferred:
                        catalog = PackageCatalog(self.conduit.importer_object_id, url)
                        for unit in units_to_download:
                            unit.downloaded = False
                            unit = self.add_rpm_unit(metadata_files, unit)
                            self.associate_rpm_unit(unit)
                            catalog.add(unit, unit.download_path)
                        continue

                    download_wrapper = packages.Packages(
                        url,
                        self.nectar_config,
                        units_to_download,
                        self.tmp_dir,
                        event_listener,
                        self._url_modify)

                    self.downloader = download_wrapper.downloader
                    _logger.info(_('Downloading %(num)s DRPMs.') % {'num': len(drpms_to_download)})
                    download_wrapper.download_packages()
                    self.downloader = None
                finally:
                    presto_file_handle.close()

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

        errata_could_not_be_merged_count = 0
        for model in package_info_generator:
            if isinstance(model, models.Errata):
                errata_controller.create_or_update_pkglist(model, self.repo.repo_id)

            try:
                model.save()
            except NotUniqueError:
                existing_unit = model.__class__.objects.filter(**model.unit_key).first()
                if additive_type:
                    try:
                        model = self._concatenate_units(existing_unit, model)
                    except ValueError:
                        # Sometimes Errata units cannot be merged and a ValueError is raised
                        # Count the errors and log them further down
                        if isinstance(model, models.Errata):
                            msg = _('The Errata "%(errata_id)s" could not be merged from the '
                                    'remote repository. This is likely due to the existing or new '
                                    'Errata not containing a valid `updated` field.')
                            _logger.debug(msg % {'errata_id': model.errata_id})
                            errata_could_not_be_merged_count += 1
                            continue
                        else:
                            raise
                    model.save()
                else:
                    # make sure the associate_unit call gets the existing unit
                    model = existing_unit

            repo_controller.associate_single_unit(self.repo, model)
        if errata_could_not_be_merged_count != 0:
            msg = _('There were %(count)d Errata units which could not be merged. This is likely '
                    'due to Errata in this repo not containing valid `updated` fields.')
            _logger.warn(msg % {'count': errata_could_not_be_merged_count})

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
            existing_unit.merge_errata(new_unit)
        else:
            raise PulpCodedException(message="Concatenation of unit type %s is not supported" %
                                             existing_unit.type_id)

        # return the unit now that we've possibly modified it.
        return existing_unit

    def _identify_wanted_versions(self, package_info_generator):
        """
        Given an iterator of Package instances available for download, scan
        through the Packages to decide which should be downloaded. If
        package_info_generator is in fact a generator, this will not consume
        much memory.

        :param package_info_generator:  iterator of pulp_rpm.plugins.db.models.Package
                                        instances
        :return:    tuple where first element is dict where keys are Packages as named tuples,
                    and values are the size of each package and second element is number of unique
                    packages
        :rtype:     tuple(dict, int)
        """
        # keys are a model's key string minus any version info
        # values are dicts where keys are serialized versions, and values are
        # a tuple of (model as named tuple, size in bytes)
        wanted = {}

        number_old_versions_to_keep = \
            self.config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
        number_of_unique_packages = 0
        for model in package_info_generator:
            versions = wanted.setdefault(model.key_string_without_version, {})
            serialized_version = model.complete_version_serialized
            info = WantedUnitInfo(model.size, model.download_path)

            if serialized_version not in versions:
                number_of_unique_packages += 1
                # if we are limited on the number of old versions we can have
                if number_old_versions_to_keep is not None:
                    number_to_keep = number_old_versions_to_keep + 1
                    if len(versions) < number_to_keep:
                        versions[serialized_version] = (model.unit_key_as_named_tuple, info)
                    else:
                        smallest_version = sorted(versions.keys(),
                                                  reverse=True)[:number_to_keep][-1]
                        if serialized_version > smallest_version:
                            del versions[smallest_version]
                            versions[serialized_version] = (model.unit_key_as_named_tuple, info)
                else:
                    versions[serialized_version] = (model.unit_key_as_named_tuple, info)

        ret = {}
        for units in wanted.itervalues():
            for unit, info in units.itervalues():
                ret[unit] = info

        return ret, number_of_unique_packages

    @staticmethod
    def _filtered_unit_generator(units, to_download=None):
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
                # We don't need to download packages twice
                to_download.remove(unit.unit_key_as_named_tuple)
                yield unit


class PackageCatalog(object):
    """
    Provides deferred catalog management for package units.

    :ivar importer_id: The import DB object ID.
    :type importer_id: bson.objectid.ObjectId
    :ivar base_url: The base URL used to download content.
    :type base_url: str
    """

    def __init__(self, importer_id, base_url):
        """
        :param importer_id: The import DB object ID.
        :type importer_id: bson.objectid.ObjectId
        :param base_url: The base URL used to download content.
        :type base_url: str
        """
        self.importer_id = importer_id
        self.base_url = base_url

    def add(self, unit, path):
        """
        Add the specified content unit to the catalog.

        :param unit: A unit being added.
        :type unit: pulp_rpm.plugins.db.models.RpmBase
        :param path: The relative path within the upstream YUM repository
#           used to construct the download URL.
        :type path: str
        """
        if not unit.storage_path:
            unit.set_storage_path(unit.filename)
        entry = LazyCatalogEntry()
        entry.path = unit.storage_path
        entry.importer_id = str(self.importer_id)
        entry.unit_id = unit.id
        entry.unit_type_id = unit.type_id
        entry.url = urljoin(self.base_url, path)
        entry.checksum = unit.checksum
        entry.checksum_algorithm = unit.checksumtype
        entry.save_revision()

    def delete(self, unit):
        """
        Remove the catalog entry for the specified unit.

        :param unit: A unit being added.
        :type unit: pulp_rpm.plugins.db.models.RpmBase
        """
        qs = LazyCatalogEntry.objects.filter(
            importer_id=str(self.importer_id),
            unit_id=unit.id,
            unit_type_id=unit.type_id)
        qs.delete()
