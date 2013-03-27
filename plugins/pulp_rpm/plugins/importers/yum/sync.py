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
from pulp_rpm.plugins.importers.download import metadata, primary, packages, presto
from pulp_rpm.plugins.importers.yum.listener import Listener
from pulp_rpm.plugins.importers.yum.report import ContentReport

_LOGGER = logging.getLogger(__name__)

def get_metadata(feed, tmp_dir):
    """

    :param feed:
    :param tmp_dir:
    :return:
    :rtype:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
    """
    metadata_files = metadata.MetadataFiles(feed, tmp_dir)
    metadata_files.download_repomd()
    metadata_files.parse_repomd()
    metadata_files.download_metadata_files()
    #metadata_files.verify_metadata_files()
    return metadata_files


def _get_metadata_file_handle(name, metadata_files):
    """

    :param metadata_files:
    :type  metadata_files:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
    :return:
    """
    file_path = metadata_files.metadata[name]['local_path']

    if file_path.endswith('.gz'):
        file_handle = gzip.open(file_path, 'r')
    elif file_path.endswith('.xz'):
        file_handle = lzma.LZMAFile(file_path, 'r')
    else:
        file_handle = open(file_path, 'r')
    return file_handle


def sync_repo(repo, sync_conduit, config):
    content_report = ContentReport()
    progress_status = {
        'metadata': {'state': 'NOT_STARTED'},
        'content': content_report,
        'errata': {'state': 'NOT_STARTED'},
        'comps': {'state': 'NOT_STARTED'},
    }
    sync_conduit.set_progress(progress_status)

    feed = config.get(constants.CONFIG_FEED_URL)
    current_units = sync_conduit.get_units()
    event_listener = Listener(sync_conduit, progress_status)
    tmp_dir = tempfile.mkdtemp()
    try:
        progress_status['metadata']['state'] = constants.STATE_RUNNING
        sync_conduit.set_progress(progress_status)

        metadata_files = get_metadata(feed, tmp_dir)
        progress_status['metadata']['state'] = constants.STATE_COMPLETE
        sync_conduit.set_progress(progress_status)

        primary_file_handle = _get_metadata_file_handle('primary', metadata_files)
        with primary_file_handle:
            # scan through all the metadata to decide which packages to download
            package_info_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            rpms_to_download, rpms_count, rpms_total_size = first_sweep(package_info_generator, current_units)

        presto_file_handle = _get_metadata_file_handle('prestodelta', metadata_files)
        with presto_file_handle:
            package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                     presto.PACKAGE_TAG,
                                                                     presto.process_package_element)
            drpms_to_download, drpms_count, drpms_total_size = first_sweep(package_info_generator, current_units)



        unit_counts = {
            'rpm': rpms_count,
            'drpm': drpms_count,
        }
        total_size = sum((rpms_total_size, drpms_total_size))
        content_report.set_initial_values(unit_counts, total_size)
        content_report['state'] = constants.STATE_RUNNING
        sync_conduit.set_progress(progress_status)


        primary_file_handle = _get_metadata_file_handle('primary', metadata_files)
        with primary_file_handle:
            package_info_generator = packages.package_list_generator(primary_file_handle,
                                                                     primary.PACKAGE_TAG,
                                                                     primary.process_package_element)
            units_to_download = _filtered_unit_generator(package_info_generator, rpms_to_download)

            packages_manager = packages.Packages(feed, units_to_download, tmp_dir, event_listener)
            packages_manager.download_packages()

        presto_file_handle = _get_metadata_file_handle('prestodelta', metadata_files)
        with presto_file_handle:
            package_info_generator = packages.package_list_generator(presto_file_handle,
                                                                     presto.PACKAGE_TAG,
                                                                     presto.process_package_element)
            units_to_download = _filtered_unit_generator(package_info_generator, drpms_to_download)

            packages_manager = packages.Packages(feed, units_to_download, tmp_dir, event_listener)
            packages_manager.download_packages()


        progress_status['content']['state'] = constants.STATE_COMPLETE
        progress_status['errata']['state'] = constants.STATE_SKIPPED
        progress_status['comps']['state'] = constants.STATE_SKIPPED
        sync_conduit.set_progress(progress_status)

        report = sync_conduit.build_success_report({}, {})
        return report

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def first_sweep(package_info_generator, current_units):
    # TODO: consider current units
    size_in_bytes = 0
    count = 0
    to_download = {}
    for pkg in package_info_generator:
        model = models.from_package_info(pkg)
        versions = to_download.setdefault(model.key_string_without_version, [])
        # TODO: if only syncing newest version, do a comparison here and evict old versions
        versions.append(model.complete_version)
        size_in_bytes += model.metadata['size']
        count += 1
    return to_download, count, size_in_bytes


def _filtered_unit_generator(units, to_download):
    for unit in units:
        # decide if this unit should be downloaded
        yield unit
