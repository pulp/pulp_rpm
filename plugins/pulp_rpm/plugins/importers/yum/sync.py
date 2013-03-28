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

import gzip
import logging
import lzma
import shutil
import tempfile

from pulp_rpm.common import constants, models
from pulp_rpm.plugins.importers.download import metadata, primary, packages, presto, updateinfo
from pulp_rpm.plugins.importers.yum.listener import DownloadListener
from pulp_rpm.plugins.importers.yum.report import ContentReport

_LOGGER = logging.getLogger(__name__)


def _get_metadata_file_handle(name, metadata_files):
    """

    :param metadata_files:
    :type  metadata_files:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
    :return:
    """
    try:
        file_path = metadata_files.metadata[name]['local_path']
    except KeyError:
        return

    if file_path.endswith('.gz'):
        file_handle = gzip.open(file_path, 'r')
    elif file_path.endswith('.xz'):
        file_handle = lzma.LZMAFile(file_path, 'r')
    else:
        file_handle = open(file_path, 'r')
    return file_handle


class RepoSync(object):
    def __init__(self, repo, sync_conduit, config):
        self.content_report = ContentReport()
        self.progress_status = {
            'metadata': {'state': 'NOT_STARTED'},
            'content': self.content_report,
            'errata': {'state': 'NOT_STARTED'},
            'comps': {'state': 'NOT_STARTED'},
        }
        sync_conduit.set_progress(self.progress_status)
        self.sync_conduit = sync_conduit
        self.config = config
        self.feed = config.get(constants.CONFIG_FEED_URL)
        self.current_units = sync_conduit.get_units()

    def run(self):
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.progress_status['metadata']['state'] = constants.STATE_RUNNING
            self.sync_conduit.set_progress(self.progress_status)
            metadata_files = self.get_metadata()
            self.progress_status['metadata']['state'] = constants.STATE_COMPLETE
            self.sync_conduit.set_progress(self.progress_status)

            self.content_report['state'] = constants.STATE_RUNNING
            self.sync_conduit.set_progress(self.progress_status)
            self.download(metadata_files)
            self.content_report['state'] = constants.STATE_COMPLETE
            self.sync_conduit.set_progress(self.progress_status)

            self.progress_status['errata']['state'] = constants.STATE_RUNNING
            self.sync_conduit.set_progress(self.progress_status)
            self.get_errata(metadata_files)
            self.progress_status['errata']['state'] = constants.STATE_COMPLETE
            self.sync_conduit.set_progress(self.progress_status)
        finally:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)


    def get_metadata(self):
        """

        :param feed:
        :param tmp_dir:
        :return:
        :rtype:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
        """
        self.sync_conduit.set_progress(self.progress_status)

        metadata_files = metadata.MetadataFiles(self.feed, self.tmp_dir)
        metadata_files.download_repomd()
        metadata_files.parse_repomd()
        metadata_files.download_metadata_files()
        #metadata_files.verify_metadata_files()
        return metadata_files


    def download(self, metadata_files):
        event_listener = DownloadListener(self.sync_conduit, self.progress_status)
        primary_file_handle = _get_metadata_file_handle('primary', metadata_files)
        with primary_file_handle:
            # scan through all the metadata to decide which packages to download
            package_info_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            rpms_to_download, rpms_count, rpms_total_size = self.first_sweep(package_info_generator, self.current_units)

        presto_file_handle = _get_metadata_file_handle('prestodelta', metadata_files)
        if presto_file_handle:
            with presto_file_handle:
                package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                drpms_to_download, drpms_count, drpms_total_size = self.first_sweep(package_info_generator, self.current_units)
        else:
            drpms_count = 0
            drpms_total_size = 0

        unit_counts = {
            'rpm': rpms_count,
            'drpm': drpms_count,
        }
        total_size = sum((rpms_total_size, drpms_total_size))
        self.content_report.set_initial_values(unit_counts, total_size)
        self.sync_conduit.set_progress(self.progress_status)


        primary_file_handle = _get_metadata_file_handle('primary', metadata_files)
        with primary_file_handle:
            package_info_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            units_to_download = self._filtered_unit_generator(package_info_generator, rpms_to_download)

            packages_manager = packages.Packages(self.feed, units_to_download, self.tmp_dir, event_listener)
            packages_manager.download_packages()

        presto_file_handle = _get_metadata_file_handle('prestodelta', metadata_files)
        if presto_file_handle:
            with presto_file_handle:
                package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                         presto.PACKAGE_TAG,
                                                                         presto.process_package_element)
                units_to_download = self._filtered_unit_generator(package_info_generator, drpms_to_download)

                packages_manager = packages.Packages(self.feed, units_to_download, self.tmp_dir, event_listener)
                packages_manager.download_packages()


        self.progress_status['content']['state'] = constants.STATE_COMPLETE
        self.progress_status['errata']['state'] = constants.STATE_RUNNING
        self.sync_conduit.set_progress(self.progress_status)



        self.progress_status['comps']['state'] = constants.STATE_SKIPPED
        self.sync_conduit.set_progress(self.progress_status)

        report = self.sync_conduit.build_success_report({}, {})
        return report


    def get_errata(self, metadata_files):
        errata_file_handle = _get_metadata_file_handle('updateinfo', metadata_files)
        if not errata_file_handle:
            return
        with errata_file_handle:
            package_info_generator = packages.package_list_generator(errata_file_handle,
                                                                     updateinfo.PACKAGE_TAG,
                                                                     updateinfo.process_package_element)
            for model in package_info_generator:
                unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, None)
                self.sync_conduit.save_unit(unit)


    def first_sweep(self, package_info_generator, current_units):
        # TODO: consider current units
        size_in_bytes = 0
        count = 0
        to_download = {}
        for model in package_info_generator:
            versions = to_download.setdefault(model.key_string_without_version, [])
            # TODO: if only syncing newest version, do a comparison here and evict old versions
            versions.append(model.complete_version)
            size_in_bytes += model.metadata['size']
            count += 1
        return to_download, count, size_in_bytes


    def _filtered_unit_generator(self, units, to_download):
        for unit in units:
            # decide if this unit should be downloaded
            yield unit
