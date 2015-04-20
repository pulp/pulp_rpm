import contextlib
import functools
import logging
import os
import shutil
import tempfile
from gettext import gettext as _
import traceback

from pulp.common.plugins import importer_constants
from pulp.plugins.util import nectar_config as nectar_utils, verification
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import existing, purge
from pulp_rpm.plugins.importers.yum.repomd import (
    metadata, primary, packages, updateinfo, presto, group, alternate)
from pulp_rpm.plugins.importers.yum.listener import ContentListener
from pulp_rpm.plugins.importers.yum.parse import treeinfo
from pulp_rpm.plugins.importers.yum.report import ContentReport, DistributionReport


_logger = logging.getLogger(__name__)


class CancelException(Exception):
    pass


class RepoSync(object):

    def __init__(self, repo, sync_conduit, call_config):
        """
        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param sync_conduit: provides access to relevant Pulp functionality
        :type  sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit

        :param call_config: plugin configuration
        :type  call_config: pulp.plugins.config.PluginCallConfiguration
        """
        self.cancelled = False
        self.working_dir = repo.working_dir
        self.content_report = ContentReport()
        self.distribution_report = DistributionReport()
        self.progress_status = {
            'metadata': {'state': 'NOT_STARTED'},
            'content': self.content_report,
            'distribution': self.distribution_report,
            'errata': {'state': 'NOT_STARTED'},
            'comps': {'state': 'NOT_STARTED'},
        }
        self.sync_conduit = sync_conduit
        self.set_progress()
        self.repo = repo

        self.call_config = call_config

        flat_call_config = call_config.flatten()
        self.nectar_config = nectar_utils.importer_config_to_nectar_config(flat_call_config)
        self.skip_repomd_steps = False
        self.current_revision = 0

    def set_progress(self):
        """
        A convenience method to perform this very repetitive task. This is also
        a convenient time to check if we've been cancelled, and if so, raise
        the proper exception.
        """
        self.sync_conduit.set_progress(self.progress_status)
        if self.cancelled is True:
            raise CancelException

    @property
    def sync_feed(self):
        """
        :return:    the URL of the feed we should sync
        :rtype:     str
        """
        repo_url = self.call_config.get(importer_constants.KEY_FEED)
        if repo_url is not None and not repo_url.endswith('/'):
            repo_url += '/'
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
        skip_config = self.call_config.get(constants.CONFIG_SKIP, [])
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
        # using this tmp dir ensures that cleanup leaves nothing behind, since
        # we delete below
        self.tmp_dir = tempfile.mkdtemp(dir=self.working_dir)
        try:
            with self.update_state(self.progress_status['metadata']):
                # Verify that we have a feed url.
                # if there is no feed url, then we have nothing to sync
                if self.sync_feed is None:
                    raise PulpCodedException(error_code=error_codes.RPM1005)

                metadata_files = self.get_metadata()
                # Save the default checksum from the metadata
                self.save_default_metadata_checksum_on_repo(metadata_files)

            with self.update_state(self.content_report) as skip:
                if not (skip or self.skip_repomd_steps):
                    self.update_content(metadata_files)

            _logger.info(_('Downloading additional units.'))

            with self.update_state(self.distribution_report, models.Distribution.TYPE) as skip:
                if not skip:
                    treeinfo.sync(self.sync_conduit, self.sync_feed, self.tmp_dir,
                                  self.nectar_config, self.distribution_report,
                                  self.set_progress)

            with self.update_state(self.progress_status['errata'], models.Errata.TYPE) as skip:
                if not (skip or self.skip_repomd_steps):
                    self.get_errata(metadata_files)

            with self.update_state(self.progress_status['comps']) as skip:
                if not (skip or self.skip_repomd_steps):
                    self.get_comps_file_units(metadata_files, group.process_group_element,
                                              group.GROUP_TAG)
                    self.get_comps_file_units(metadata_files, group.process_category_element,
                                              group.CATEGORY_TAG)
                    self.get_comps_file_units(metadata_files, group.process_environment_element,
                                              group.ENVIRONMENT_TAG)

        except CancelException:
            report = self.sync_conduit.build_cancel_report(self._progress_summary,
                                                           self.progress_status)
            report.canceled_flag = True
            return report

        except Exception, e:
            for step, value in self.progress_status.iteritems():
                if value.get('state') == constants.STATE_RUNNING:
                    value['state'] = constants.STATE_FAILED
                    value['error'] = str(e)
            self.set_progress()
            if isinstance(e, PulpCodedException):
                raise
            report = self.sync_conduit.build_failure_report(self._progress_summary,
                                                            self.progress_status)
            return report

        finally:
            # clean up whatever we may have left behind
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

        self.save_repomd_revision()
        _logger.info(_('Sync complete.'))
        return self.sync_conduit.build_success_report(self._progress_summary, self.progress_status)

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
        for step_name, progress_dict in self.progress_status.iteritems():
            ret[step_name] = {'state': progress_dict['state']}
        return ret

    def get_metadata(self):
        """
        :return:    instance of MetadataFiles where each relevant file has been
                    identified and downloaded.
        :rtype:     pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        _logger.info(_('Downloading metadata from %(feed)s.') % {'feed': self.sync_feed})
        metadata_files = metadata.MetadataFiles(self.sync_feed, self.tmp_dir, self.nectar_config)
        # allow the downloader to be accessed by the cancel method if necessary
        self.downloader = metadata_files.downloader
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

        scratchpad = self.sync_conduit.get_scratchpad() or {}
        previous_revision = scratchpad.get(constants.REPOMD_REVISION_KEY, 0)
        previous_skip_set = set(scratchpad.get(constants.PREVIOUS_SKIP_LIST, []))
        current_skip_set = set(self.call_config.get(constants.CONFIG_SKIP, []))
        self.current_revision = metadata_files.revision
        # if the revision hasn't increased and the skip list doesn't include new types that weren't
        # present on the last run...
        if metadata_files.revision <= previous_revision \
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
            scratchpad = self.sync_conduit.get_scratchpad() or {}
            scratchpad[constants.REPOMD_REVISION_KEY] = self.current_revision
            # we save the skip list so if one of the types contained in it gets removed, the next
            # sync will know to not skip based on repomd revision
            scratchpad[constants.PREVIOUS_SKIP_LIST] = self.call_config.get(
                constants.CONFIG_SKIP, [])
            self.sync_conduit.set_scratchpad(scratchpad)

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
            scratchpad = self.sync_conduit.get_repo_scratchpad()
            scratchpad[constants.SCRATCHPAD_DEFAULT_METADATA_CHECKSUM] = checksum_type
            self.sync_conduit.set_repo_scratchpad(scratchpad)

    def import_unknown_metadata_files(self, metadata_files):
        """
        Import metadata files whose type is not known to us. These are any files
        that we are not already parsing.

        :param metadata_files:  object containing access to all metadata files
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        for metadata_type, file_info in metadata_files.metadata.iteritems():
            if metadata_type not in metadata_files.KNOWN_TYPES:
                checksum_type = file_info['checksum']['algorithm']
                checksum_type = verification.sanitize_checksum_type(checksum_type)

                unit_metadata = {
                    'checksum': file_info['checksum']['hex_digest'],
                    'checksum_type': checksum_type,
                }
                model = models.YumMetadataFile(metadata_type,
                                               self.sync_conduit.repo_id,
                                               unit_metadata)
                relative_path = os.path.join(model.relative_dir,
                                             os.path.basename(file_info['local_path']))
                unit = self.sync_conduit.init_unit(models.YumMetadataFile.TYPE, model.unit_key,
                                                   model.metadata, relative_path)
                shutil.copyfile(file_info['local_path'], unit.storage_path)
                self.sync_conduit.save_unit(unit)

    def update_content(self, metadata_files):
        """
        Decides what to download and then downloads it

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        rpms_to_download, drpms_to_download = self._decide_what_to_download(metadata_files)
        self.download(metadata_files, rpms_to_download, drpms_to_download)
        # removes unwanted units according to the config settings
        purge.purge_unwanted_units(metadata_files, self.sync_conduit, self.call_config)

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
        if models.RPM.TYPE in self.call_config.get(constants.CONFIG_SKIP, []):
            _logger.debug('skipping RPM sync')
            return set(), 0, 0
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)
        try:
            # scan through all the metadata to decide which packages to download
            package_info_generator = packages.package_list_generator(
                primary_file_handle, primary.PACKAGE_TAG, primary.process_package_element)
            wanted = self._identify_wanted_versions(package_info_generator)
            # check for the units that are already in the repo
            not_found_in_the_repo = existing.check_repo(wanted.iterkeys(),
                                                        self.sync_conduit.get_units)
            # check for the units that are not in the repo, but exist on the server
            # and associate them to the repo
            to_download = existing.check_all_and_associate(not_found_in_the_repo,
                                                           self.sync_conduit)
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
        if models.DRPM.TYPE in self.call_config.get(constants.CONFIG_SKIP, []):
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
                    # check for the units that are already in the repo
                    not_found_in_the_repo = existing.check_repo(wanted.iterkeys(),
                                                                self.sync_conduit.get_units)
                    # check for the units that are not in the repo, but exist on the server
                    # and associate them to the repo
                    to_download = existing.check_all_and_associate(not_found_in_the_repo,
                                                                   self.sync_conduit)
                    count += len(to_download)
                    for unit in to_download:
                        size += wanted[unit]
                finally:
                    presto_file_handle.close()

        return to_download, count, size

    def download(self, metadata_files, rpms_to_download, drpms_to_download):
        """
        Actually download the requested RPMs and DRPMs. This method iterates over
        the appropriate metadata file and downloads those items which are present
        in the corresponding set. It also checks for the RPMs and DRPMs which exist
        in other repositories before downloading them. If they are already downloaded,
        we skip the download and just associate them to the given repository.

        :param metadata_files:      populated instance of MetadataFiles
        :type  metadata_files:      pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param rpms_to_download:    set of RPM.NAMEDTUPLEs
        :type  rpms_to_download:    set
        :param drpms_to_download:   set of DRPM.NAMEDTUPLEs
        :type  drpms_to_download:   set

        :rtype: pulp.plugins.model.SyncReport
        """
        # TODO: probably should make this more generic
        event_listener = ContentListener(self.sync_conduit, self.progress_status, self.call_config,
                                         metadata_files)
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)
        try:
            package_model_generator = packages.package_list_generator(
                primary_file_handle, primary.PACKAGE_TAG, primary.process_package_element)
            units_to_download = self._filtered_unit_generator(package_model_generator,
                                                              rpms_to_download)

            download_wrapper = alternate.Packages(self.sync_feed, self.nectar_config,
                                                  units_to_download, self.tmp_dir, event_listener)
            # allow the downloader to be accessed by the cancel method if necessary
            self.downloader = download_wrapper.downloader
            _logger.info(_('Downloading %(num)s RPMs.') % {'num': len(rpms_to_download)})
            download_wrapper.download_packages()
            self.downloader = None
        finally:
            primary_file_handle.close()

        # download DRPMs
        # multiple options for deltainfo files depending on the distribution
        # so we have to go through all of them to get all the DRPMs
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

                    download_wrapper = packages.Packages(self.sync_feed, self.nectar_config,
                                                         units_to_download, self.tmp_dir,
                                                         event_listener)
                    # allow the downloader to be accessed by the cancel method if necessary
                    self.downloader = download_wrapper.downloader
                    _logger.info(_('Downloading %(num)s DRPMs.') % {'num': len(drpms_to_download)})
                    download_wrapper.download_packages()
                    self.downloader = None
                finally:
                    presto_file_handle.close()

        report = self.sync_conduit.build_success_report({}, {})
        return report

    def cancel(self):
        """
        Cancels the current sync. Looks for a "downloader" object and calls its
        "cancel" method, and then triggers a progress report.
        """
        self.cancelled = True
        for step, value in self.progress_status.iteritems():
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
            process_func = functools.partial(processing_function, self.repo.id)

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
            wanted = (model.as_named_tuple for model in package_info_generator)
            # given what we want, filter out what we already have
            to_save = existing.check_repo(wanted, self.sync_conduit.get_units)

            # rewind, iterate again through the file, and save what we need
            file_handle.seek(0)
            all_packages = packages.package_list_generator(file_handle,
                                                           tag,
                                                           process_func)
            package_info_generator = \
                (model for model in all_packages if model.as_named_tuple in to_save)

        for model in package_info_generator:
            unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, None)
            if additive_type:
                existing_unit = self.sync_conduit.find_unit_by_unit_key(model.TYPE, model.unit_key)
                if existing_unit:
                    unit = self._concatenate_units(existing_unit, unit)

            self.sync_conduit.save_unit(unit)

    def _concatenate_units(self, existing_unit, new_unit):
        """
        Perform unit concatenation.

        :param existing_unit: The unit that is already in the DB
        :type  existing_unit: pulp.plugins.model.Unit

        :param new_unit: The unit we are combining with the existing unit
        :type  new_unit: pulp.plugins.model.Unit
        """
        if existing_unit.type_id != new_unit.type_id:
            raise PulpCodedException(message="Cannot concatenate two units of different types. "
                                             "Tried to concatenate %s with %s" %
                                             (existing_unit.type_id, new_unit.type_id))

        if existing_unit.unit_key != new_unit.unit_key:
            raise PulpCodedException(message="Concatenated units must have the same unit key. "
                                             "Tried to concatenate %s with %s" %
                                             (existing_unit.unit_key, new_unit.unit_key))

        if existing_unit.type_id == ids.TYPE_ID_ERRATA:
            # add in anything from new_unit that we don't already have. We key
            # package lists by name for this concatenation.
            existing_package_list_names = [p['name'] for p in existing_unit.metadata['pkglist']]

            for possible_new_pkglist in new_unit.metadata['pkglist']:
                if possible_new_pkglist['name'] not in existing_package_list_names:
                    existing_unit.metadata['pkglist'] += [possible_new_pkglist]
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
            self.call_config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
        for model in package_info_generator:
            versions = wanted.setdefault(model.key_string_without_version, {})
            serialized_version = model.complete_version_serialized
            size = model.metadata['size']

            # if we are limited on the number of old versions we can have,
            if number_old_versions_to_keep is not None:
                number_to_keep = number_old_versions_to_keep + 1
                if len(versions) < number_to_keep:
                    versions[serialized_version] = (model.as_named_tuple, size)
                else:
                    smallest_version = sorted(versions.keys(), reverse=True)[:number_to_keep][-1]
                    if serialized_version > smallest_version:
                        del versions[smallest_version]
                        versions[serialized_version] = (model.as_named_tuple, size)
            else:
                versions[serialized_version] = (model.as_named_tuple, size)
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
            elif unit.as_named_tuple in to_download:
                yield unit
