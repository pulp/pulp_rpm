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

import functools
import logging
import shutil
import tempfile

from pulp.common.plugins import importer_constants
from pulp.plugins.model import SyncReport
from pulp.plugins.util import nectar_config as nectar_utils

from pulp_rpm.common import constants, models
from pulp_rpm.plugins.importers.yum import existing, purge
from pulp_rpm.plugins.importers.yum.repomd import metadata, primary, packages, updateinfo, presto, group
from pulp_rpm.plugins.importers.yum.listener import ContentListener
from pulp_rpm.plugins.importers.yum.parse import treeinfo
from pulp_rpm.plugins.importers.yum.report import ContentReport, DistributionReport


_LOGGER = logging.getLogger(__name__)


class CancelException(Exception):
    pass


class FailedException(Exception):
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
        if not repo_url.endswith('/'):
            repo_url += '/'
        return repo_url

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
            self.progress_status['metadata']['state'] = constants.STATE_RUNNING
            self.set_progress()
            metadata_files = self.get_metadata()
            if self.progress_status['metadata']['state'] == constants.STATE_RUNNING:
                self.progress_status['metadata']['state'] = constants.STATE_COMPLETE
            self.set_progress()

            self.content_report['state'] = constants.STATE_RUNNING
            self.set_progress()
            self.update_content(metadata_files)
            if self.content_report['state'] == constants.STATE_RUNNING:
                self.content_report['state'] = constants.STATE_COMPLETE
            self.set_progress()

            if models.Distribution.TYPE in self.call_config.get(constants.CONFIG_SKIP, []):
                self.distribution_report['state'] = constants.STATE_SKIPPED
            else:
                self.distribution_report['state'] = constants.STATE_RUNNING
                self.set_progress()
                treeinfo.sync(self.sync_conduit, self.sync_feed,
                              self.tmp_dir, self.distribution_report, self.set_progress)
            self.set_progress()

            if models.Errata.TYPE in self.call_config.get(constants.CONFIG_SKIP, []):
                self.progress_status['errata']['state'] = constants.STATE_SKIPPED
            else:
                self.progress_status['errata']['state'] = constants.STATE_RUNNING
                self.set_progress()
                self.get_errata(metadata_files)
                self.progress_status['errata']['state'] = constants.STATE_COMPLETE
            self.set_progress()

            self.progress_status['comps']['state'] = constants.STATE_RUNNING
            self.set_progress()
            self.get_groups(metadata_files)
            self.get_categories(metadata_files)
            self.progress_status['comps']['state'] = constants.STATE_COMPLETE
            self.set_progress()

        except CancelException:
            report = self.sync_conduit.build_cancel_report(self._progress_summary, self.progress_status)
            report.canceled_flag = True
            return report

        except Exception, e:
            for step, value in self.progress_status.iteritems():
                if value.get('state') == constants.STATE_RUNNING:
                    value['state'] = constants.STATE_FAILED
                    value['error'] = str(e)
            self.set_progress()
            report = self.sync_conduit.build_failure_report(self._progress_summary, self.progress_status)
            return report

        finally:
            # clean up whatever we may have left behind
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

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
        metadata_files = metadata.MetadataFiles(self.sync_feed, self.tmp_dir, self.nectar_config)
        # allow the downloader to be accessed by the cancel method if necessary
        self.downloader = metadata_files.downloader
        try:
            metadata_files.download_repomd()
        except IOError, e:
            raise FailedException(str(e))

        try:
            metadata_files.parse_repomd()
        except ValueError, e:
            raise FailedException(str(e))

        metadata_files.download_metadata_files()
        self.downloader = None
        metadata_files.generate_dbs()
        # TODO: verify metadata
        #metadata_files.verify_metadata_files()
        return metadata_files

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
        rpms_to_download, rpms_count, rpms_total_size = self._decide_rpms_to_download(metadata_files)
        drpms_to_download, drpms_count, drpms_total_size = self._decide_drpms_to_download(metadata_files)

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
            _LOGGER.debug('skipping RPM sync')
            return set(), 0, 0
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)
        try:
            # scan through all the metadata to decide which packages to download
            package_info_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            wanted = self._identify_wanted_versions(package_info_generator)
            to_download = existing.check_repo(wanted.iterkeys(), self.sync_conduit.get_units)
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
            _LOGGER.debug('skipping DRPM sync')
            return set(), 0, 0
        presto_file_handle = metadata_files.get_metadata_file_handle(presto.METADATA_FILE_NAME)
        if presto_file_handle:
            try:
                package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                wanted = self._identify_wanted_versions(package_info_generator)
                to_download = existing.check_repo(wanted.iterkeys(), self.sync_conduit.get_units)
                count = len(to_download)
                size = 0
                for unit in to_download:
                    size += wanted[unit]
            finally:
                presto_file_handle.close()
        else:
            to_download = set()
            count = 0
            size = 0
        return to_download, count, size

    def download(self, metadata_files, rpms_to_download, drpms_to_download):
        """
        Actually download the requested RPMs and DRPMs. This method iterates over
        the appropriate metadata file and downloads those items which are present
        in the corresponding set.

        :param metadata_files:      populated instance of MetadataFiles
        :type  metadata_files:      pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        :param rpms_to_download:    set of RPM.NAMEDTUPLEs
        :type  rpms_to_download:    set
        :param drpms_to_download:   set of DRPM.NAMEDTUPLEs
        :type  drpms_to_download:   set

        :rtype: pulp.plugins.model.SyncReport
        """
        # TODO: probably should make this more generic
        event_listener = ContentListener(self.sync_conduit, self.progress_status, self.call_config, metadata_files)
        primary_file_handle = metadata_files.get_metadata_file_handle(primary.METADATA_FILE_NAME)
        try:
            package_model_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            units_to_download = self._filtered_unit_generator(package_model_generator, rpms_to_download)

            download_wrapper = packages.Packages(self.sync_feed, self.nectar_config,
                                                    units_to_download, self.tmp_dir, event_listener)
            # allow the downloader to be accessed by the cancel method if necessary
            self.downloader = download_wrapper.downloader
            download_wrapper.download_packages()
            self.downloader = None
        finally:
            primary_file_handle.close()

        # download DRPMs
        presto_file_handle = metadata_files.get_metadata_file_handle(presto.METADATA_FILE_NAME)
        if presto_file_handle:
            try:
                package_model_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                units_to_download = self._filtered_unit_generator(package_model_generator, drpms_to_download)

                download_wrapper = packages.Packages(self.sync_feed, self.nectar_config,
                                                        units_to_download, self.tmp_dir, event_listener)
                # allow the downloader to be accessed by the cancel method if necessary
                self.downloader = download_wrapper.downloader
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
            _LOGGER.debug('could not cancel downloader')
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
            _LOGGER.debug('updateinfo not found')
            return
        try:
            self.save_fileless_units(errata_file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)

        finally:
            errata_file_handle.close()

    def get_groups(self, metadata_files):
        """
        Given repo metadata files, decides which groups to get and gets them
        based on importer config settings.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
            _LOGGER.debug('comps metadata not found')
            return

        try:
            process_func = functools.partial(group.process_group_element, self.repo.id)

            self.save_fileless_units(group_file_handle, group.GROUP_TAG, process_func)
        finally:
            group_file_handle.close()

    def get_categories(self, metadata_files):
        """
        Given repo metadata files, decides which categories to get and gets them
        based on importer config settings.

        :param metadata_files:  instance of MetadataFiles
        :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
        """
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
            _LOGGER.debug('comps metadata not found')
            return

        try:
            process_func = functools.partial(group.process_category_element, self.repo.id)
            self.save_fileless_units(group_file_handle, group.CATEGORY_TAG, process_func)
        finally:
            group_file_handle.close()

    def save_fileless_units(self, file_handle, tag, process_func):
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
        :type process_func:     function
        """
        # iterate through the file and determine what we want to have
        package_info_generator = packages.package_list_generator(file_handle,
                                                                 tag,
                                                                 process_func)
        wanted = (model.as_named_tuple for model in package_info_generator)
        # given what we want, filter out what we already have
        to_save = existing.check_repo(wanted, self.sync_conduit.get_units)

        # rewind, iterate again through the file, and download what we need
        file_handle.seek(0)
        package_info_generator = packages.package_list_generator(file_handle,
                                                                 tag,
                                                                 process_func)
        for model in package_info_generator:
            if model.as_named_tuple in to_save:
                unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, None)
                self.sync_conduit.save_unit(unit)

    def _identify_wanted_versions(self, package_info_generator):
        """
        Given an iterator of Package instances available for download, scan
        through the Packages to decide which should be downloaded. If
        package_info_generator is in fact a generator, this will not consume
        much memory.

        :param package_info_generator:  iterator of pulp_rpm.common.models.Package
                                        instances
        :return:    dict where keys are Packages as named tuples, and values
                    are the size of each package
        :rtype:     dict
        """
        # keys are a model's key string minus any version info
        # values are dicts where keys are serialized versions, and values are
        # a tuple of (model as named tuple, size in bytes)
        wanted = {}

        number_old_versions_to_keep = self.call_config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
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

        :param units:       iterator of pulp_rpm.common.models.Package instances
        :type  units:       iterator
        :param to_download: collection (preferably a set) of Packages as named
                            tuples that we want to download
        :type  to_download: set

        :return:    generator of pulp_rpm.common.models.Package instances that
                    should be downloaded
        :rtype:     generator
        """
        for unit in units:
            if to_download is None:
                # assume we want to download everything
                yield unit
            elif unit.as_named_tuple in to_download:
                yield unit
