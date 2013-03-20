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
import shutil
import tempfile
from pulp_rpm.plugins.importers.yum.report import ContentReport

from pulp_rpm.common import constants, models
from pulp_rpm.plugins.importers.download import metadata, primary, packages
from pulp_rpm.plugins.importers.yum.listener import Listener


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


def _get_primary_metadata_file_handle(metadata_files):
    """

    :param metadata_files:
    :type  metadata_files:  pulp_rpm.plugins.importers.download.metadata.MetadataFiles
    :return:
    """
    primary_file_path = metadata_files.metadata['primary']['local_path']

    if primary_file_path.endswith('.gz'):
        primary_file_handle = gzip.open(primary_file_path, 'r')
    else:
        primary_file_handle = open(primary_file_path, 'r')
    return primary_file_handle


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
    event_listener = Listener(sync_conduit)
    tmp_dir = tempfile.mkdtemp()
    try:
        progress_status['metadata']['state'] = constants.STATE_RUNNING
        sync_conduit.set_progress(progress_status)

        metadata_files = get_metadata(feed, tmp_dir)
        primary_file_handle = _get_primary_metadata_file_handle(metadata_files)

        progress_status['metadata']['state'] = constants.STATE_COMPLETE
        sync_conduit.set_progress(progress_status)

        content_report['state'] = constants.STATE_RUNNING
        sync_conduit.set_progress(progress_status)
        with primary_file_handle:
            # scan through all the metadata to decide which packages to download
            package_info_generator = primary.primary_package_list_generator(primary_file_handle)
            to_download, unit_counts, total_size = first_sweep(package_info_generator, current_units)

            primary_file_handle.seek(0)
            package_info_generator = primary.primary_package_list_generator(primary_file_handle)
            units_to_download = _filtered_unit_generator(package_info_generator, to_download)

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
    counts = {
        models.RPM: 0,
        models.SRPM: 0,
        models.DRPM: 0,
    }
    size_in_bytes = 0
    to_download = {}
    for pkg in package_info_generator:
        model = models.from_package_info(pkg)
        versions = to_download.setdefault(model.key_string_without_version, [])
        # TODO: if only syncing newest version, do a comparison here and evict old versions
        versions.append(model.version)
        counts[model.TYPE] += 1
        size_in_bytes += model.metadata['size']
    return to_download, counts, size_in_bytes


def _filtered_unit_generator(units, to_download):
    for unit in units:
        # decide if this unit should be downloaded
        yield unit
