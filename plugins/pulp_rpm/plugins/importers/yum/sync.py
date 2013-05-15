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
from pulp.plugins.util import downloader_config as nectar_utils

from pulp_rpm.common import constants
from pulp_rpm.plugins.importers.yum import existing
from pulp_rpm.plugins.importers.yum.repomd import metadata, primary, packages, updateinfo, presto, group
from pulp_rpm.plugins.importers.yum.listener import ContentListener
from pulp_rpm.plugins.importers.yum.parse import treeinfo
from pulp_rpm.plugins.importers.yum.report import ContentReport, DistributionReport


_LOGGER = logging.getLogger(__name__)


class CancelException(Exception):
    pass


class RepoSync(object):

    def __init__(self, repo, sync_conduit, call_config):
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
        self.sync_conduit.set_progress(self.progress_status)
        if self.cancelled is True:
            raise CancelException

    @property
    def sync_feed(self):
        return self.call_config.get(importer_constants.KEY_FEED)

    def run(self):
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
            self.get_content(metadata_files)
            if self.content_report['state'] == constants.STATE_RUNNING:
                self.content_report['state'] = constants.STATE_COMPLETE
            self.set_progress()

            self.distribution_report['state'] = constants.STATE_RUNNING
            self.set_progress()
            treeinfo.sync(self.sync_conduit, self.sync_feed,
                          self.tmp_dir, self.distribution_report, self.set_progress)
            self.set_progress()

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
            report = SyncReport(False, self.content_report['items_total'], 0, 0, self.progress_status, self.progress_status)
            report.canceled_flag = True
            return report

        finally:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

        return SyncReport(True, self.content_report['items_total'], 0, 0, {}, self.progress_status)

    def get_metadata(self):
        """

        :return:
        :rtype:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
        """
        metadata_files = metadata.MetadataFiles(self.sync_feed, self.tmp_dir)
        # allow the downloader to be accessed by the cancel method if necessary
        self.downloader = metadata_files.downloader
        metadata_files.download_repomd()
        metadata_files.parse_repomd()
        metadata_files.download_metadata_files()
        self.downloader = None
        # TODO: verify metadata
        #metadata_files.verify_metadata_files()
        return metadata_files

    def get_content(self, metadata_files):
        rpms_to_download, drpms_to_download = self._decide_what_to_download(metadata_files)
        self.download(metadata_files, rpms_to_download, drpms_to_download)

    def _decide_what_to_download(self, metadata_files):
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
        primary_file_handle = metadata_files.get_metadata_file_handle('primary')
        with primary_file_handle:
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

    def _decide_drpms_to_download(self, metadata_files):
        presto_file_handle = metadata_files.get_metadata_file_handle('prestodelta')
        if presto_file_handle:
            with presto_file_handle:
                package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                wanted = self._identify_wanted_versions(package_info_generator)
                to_download = existing.check_repo(wanted.iterkeys(), self.sync_conduit.get_units)
                count = len(to_download)
                size = 0
                for unit in to_download:
                    size += wanted[unit]
        else:
            to_download = set()
            count = 0
            size = 0
        return to_download, count, size

    def download(self, metadata_files, rpms_to_download, drpms_to_download):
        # TODO: probably should make this more generic
        event_listener = ContentListener(self.sync_conduit, self.progress_status, self.call_config)
        primary_file_handle = metadata_files.get_metadata_file_handle('primary')
        with primary_file_handle:
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

        presto_file_handle = metadata_files.get_metadata_file_handle('prestodelta')
        if presto_file_handle:
            with presto_file_handle:
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

        report = self.sync_conduit.build_success_report({}, {})
        return report

    def cancel(self):
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
        except CancelException:
            pass

    def get_errata(self, metadata_files):
        errata_file_handle = metadata_files.get_metadata_file_handle('updateinfo')
        if not errata_file_handle:
            _LOGGER.debug('updateinfo not found')
            return
        package_keys = []
        for model in self.get_general(errata_file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element):
            package_keys.extend(model.package_unit_keys)

        # TODO: get packages from package_keys

    def get_groups(self, metadata_files):
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
        # TODO: log something?
            return
        process_func = functools.partial(group.process_group_element, self.repo.id)

        names = set()
        for model in self.get_general(group_file_handle, group.GROUP_TAG, process_func):
            names.update(model.all_package_names)
        # TODO: get named RPMS

    def get_categories(self, metadata_files):
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
        # TODO: log something?
            return

        group_names = set()
        process_func = functools.partial(group.process_category_element, self.repo.id)
        for model in self.get_general(group_file_handle, group.CATEGORY_TAG, process_func):
            group_names.update(model.group_names)
        # TODO: get groups

    def get_general(self, file_handle, tag, process_func):
        with file_handle:
            # iterate through file and determine what we want to have
            package_info_generator = packages.package_list_generator(file_handle,
                                                                     tag,
                                                                     process_func)
            wanted = (model.as_named_tuple for model in package_info_generator)
            to_download = existing.check_repo(wanted, self.sync_conduit.get_units)

            # rewind, iterate again through the file, and download what we need
            file_handle.seek(0)
            package_info_generator = packages.package_list_generator(file_handle,
                                                                     tag,
                                                                     process_func)
            for model in package_info_generator:
                if model.as_named_tuple in to_download:
                    unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, None)
                    self.sync_conduit.save_unit(unit)
                    yield model

    def _identify_wanted_versions(self, package_info_generator):
        """
        Given an iterator of Package instances available for download, and a list
        of units currently in the repo, scan through the Packages to decide which
        should be downloaded. If package_info_generator is in fact a generator,
        this will not consume much memory.

        :param package_info_generator:
        :return:
        :rtype:     dict
        """
        # TODO: consider current units
        wanted = {}
        for model in package_info_generator:
            versions = wanted.setdefault(model.key_string_without_version, {})
            serialized_version = model.complete_version_serialized
            size = model.metadata['size']
            if self.call_config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT) == 0:
                if not versions or serialized_version > max(versions.keys()):
                    versions.clear()
                    versions[serialized_version] = (model.as_named_tuple, size)
            else:
                versions[serialized_version] = (model.as_named_tuple, size)
        ret = {}
        for units in wanted.itervalues():
            for unit, size in units.itervalues():
                ret[unit] = size

        return ret

    def _filtered_unit_generator(self, units, to_download=None):
        for unit in units:
            # TODO: decide if this unit should be downloaded
            if to_download is None:
                # assume we want to download everything
                yield unit
            elif unit.as_named_tuple in to_download:
                yield unit
