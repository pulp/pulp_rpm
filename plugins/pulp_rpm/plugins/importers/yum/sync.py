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

from pulp.plugins.model import SyncReport

from pulp_rpm.common import constants
from pulp_rpm.plugins.importers.yum.repomd import metadata, primary, packages, updateinfo, presto, group
from pulp_rpm.plugins.importers.yum.listener import ContentListener
from pulp_rpm.plugins.importers.yum.parse import treeinfo
from pulp_rpm.plugins.importers.yum.report import ContentReport, DistributionReport

_LOGGER = logging.getLogger(__name__)


class RepoSync(object):
    def __init__(self, repo, sync_conduit, config):
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
        self.set_progress = functools.partial(self.sync_conduit.set_progress, self.progress_status)
        self.set_progress()
        self.config = config
        self.current_units = sync_conduit.get_units()
        self.repo = repo

    def run(self):
        # using this tmp dir ensures that cleanup leaves nothing behind, since
        # we delete below
        self.tmp_dir = tempfile.mkdtemp(dir=self.working_dir)
        try:
            self.progress_status['metadata']['state'] = constants.STATE_RUNNING
            self.set_progress()
            metadata_files = self.get_metadata()
            self.progress_status['metadata']['state'] = constants.STATE_COMPLETE
            self.set_progress()

            self.content_report['state'] = constants.STATE_RUNNING
            self.set_progress()
            self.get_content(metadata_files)
            self.content_report['state'] = constants.STATE_COMPLETE
            self.set_progress()

            self.distribution_report['state'] = constants.STATE_RUNNING
            self.set_progress()
            treeinfo.sync(self.sync_conduit, self.config.feed, self.tmp_dir, self.distribution_report, self.set_progress)
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

        finally:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

        return SyncReport(True, self.content_report['items_total'], 0, 0, {}, self.progress_status)

    def get_metadata(self):
        """

        :return:
        :rtype:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
        """
        metadata_files = metadata.MetadataFiles(self.config.feed, self.tmp_dir)
        metadata_files.download_repomd()
        metadata_files.parse_repomd()
        metadata_files.download_metadata_files()
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
            return self._identify_wanted_packages(package_info_generator, self.current_units)

    def _decide_drpms_to_download(self, metadata_files):
        presto_file_handle = metadata_files.get_metadata_file_handle('prestodelta')
        if presto_file_handle:
            with presto_file_handle:
                package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                drpms_to_download, drpms_count, drpms_total_size = self._identify_wanted_packages(package_info_generator, self.current_units)
        else:
            drpms_to_download = []
            drpms_count = 0
            drpms_total_size = 0
        return drpms_to_download, drpms_count, drpms_total_size

    def download(self, metadata_files, rpms_to_download, drpms_to_download):
        # TODO: probably should make this more generic
        event_listener = ContentListener(self.sync_conduit, self.progress_status)
        primary_file_handle = metadata_files.get_metadata_file_handle('primary')
        with primary_file_handle:
            package_model_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            units_to_download = self._filtered_unit_generator(package_model_generator, rpms_to_download)

            packages_downloader = packages.Packages(self.config.feed, units_to_download, self.tmp_dir, event_listener)
            packages_downloader.download_packages()

        presto_file_handle = metadata_files.get_metadata_file_handle('prestodelta')
        if presto_file_handle:
            with presto_file_handle:
                package_model_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                units_to_download = self._filtered_unit_generator(package_model_generator, drpms_to_download)

                packages_downloader = packages.Packages(self.config.feed, units_to_download, self.tmp_dir, event_listener)
                packages_downloader.download_packages()

        report = self.sync_conduit.build_success_report({}, {})
        return report

    def get_errata(self, metadata_files):
        errata_file_handle = metadata_files.get_metadata_file_handle('updateinfo')
        if not errata_file_handle:
            return
        return self.get_general(errata_file_handle, updateinfo.process_package_element, updateinfo.PACKAGE_TAG)

    def get_groups(self, metadata_files):
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
        # TODO: log something?
            return
        process_func = functools.partial(group.process_group_element, self.repo.id)
        return self.get_general(group_file_handle, group.GROUP_TAG, process_func)

    def get_categories(self, metadata_files):
        group_file_handle = metadata_files.get_group_file_handle()
        if group_file_handle is None:
        # TODO: log something?
            return

        process_func = functools.partial(group.process_category_element, self.repo.id)
        return self.get_general(group_file_handle, group.CATEGORY_TAG, process_func)

    def get_general(self, file_handle, tag, process_func):
        with file_handle:
            package_info_generator = packages.package_list_generator(file_handle,
                                                                     tag,
                                                                     process_func)
            for model in package_info_generator:
                unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, None)
                self.sync_conduit.save_unit(unit)

    def _identify_wanted_packages(self, package_info_generator, current_units):
        """
        Given an iterator of Package instances available for download, and a list
        of units currently in the repo, scan through the Packages to decide which
        should be downloaded. If package_info_generator is in fact a generator,
        this will not consume much memory.

        :param package_info_generator:
        :param current_units:
        :return:
        """
        # TODO: consider current units
        to_download = {}
        sizes_in_bytes = {}
        for model in package_info_generator:
            versions = to_download.setdefault(model.key_string_without_version, set())
            serialized_version = model.complete_version_serialized
            if self.config.newest:
                if not versions or serialized_version > max(versions):
                    versions.clear()
                    versions.add(serialized_version)
                    sizes_in_bytes[model.key_string_without_version] = [model.metadata['size']]
            else:
                versions.add(serialized_version)
                sizes_in_bytes.setdefault(model.key_string_without_version, []).append(model.metadata['size'])

        count = 0
        size_in_bytes = 0
        for value in sizes_in_bytes.itervalues():
            count += len(value)
            size_in_bytes += sum(value)
        return to_download, count, size_in_bytes

    def _filtered_unit_generator(self, units, to_download=None):
        for unit in units:
            # TODO: decide if this unit should be downloaded
            if to_download is None:
                yield unit
            versions = to_download.get(unit.key_string_without_version, set())
            if unit.complete_version_serialized in versions:
                yield unit
