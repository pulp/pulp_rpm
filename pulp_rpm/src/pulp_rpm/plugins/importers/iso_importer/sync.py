# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
import errno
import logging
import os
import shutil

from pulp_rpm.common import constants, ids
from pulp_rpm.common.constants import STATE_RUNNING, STATE_COMPLETE
from pulp_rpm.common.sync_progress import SyncProgressReport
from pulp_rpm.plugins.importers.iso_importer import configuration
from pulp_rpm.plugins.importers.iso_importer.bumper import ISOBumper

from pulp.common.util import encode_unicode
from pulp.plugins.conduits.mixins import UnitAssociationCriteria
import pulp.server.util

logger = logging.getLogger(__name__)


# TODO: Remove dangling symlinks when remove units is called, or when syncing finds that files have
#       been removed from the upstream repo

# TODO: Delete the PULP_MANIFEST file after sync.

# Grinder doesn't allow us to get the manifest before downloading content, and it also doesn't allow
# us to prescribe how the files should be laid out in the fs. We originally designed this module to
# simply retrieve the files from Grinder and then move them to the final destination path, but that
# design led to Grinder downloading the entire repository on each run, since there is also no API to
# tell Grinder which files have already been downloaded. Due to all of these circumstances, we need
# to have Grinder download the content to the final destination instead of downloading it to a
# temporary working location. jdob and I talked, and we decided to just hardcode this path for now,
# and in the future we can reimplement Grinder to work in a more favorable fashion. Hardcoding the
# path is necessary, because we cannot use init_unit to get the path from Pulp since we need the
# path before Grinder does anything.

# TODO: Reproduce folder structures that may have been found on the server
# TODO: optionally delete Units that we have that weren't found in the repo
# TODO: optionally don't check the checksum and size
def perform_sync(repo, sync_conduit, config):
    """
    Perform the sync operation accoring to the config for the given repo, and return a report. The
    sync progress will be reported through the sync_conduit.

    :rtype: pulp.plugins.model.SyncReport
    """
    progress_report = SyncProgressReport(sync_conduit)
    progress_report.metadata_state = STATE_RUNNING
    progress_report.modules_state = STATE_RUNNING

    max_speed = config.get(constants.CONFIG_MAX_SPEED)
    if max_speed is not None:
        max_speed = float(max_speed)
    num_threads = config.get(constants.CONFIG_NUM_THREADS)
    if num_threads is not None:
        num_threads = int(num_threads)
    bumper = ISOBumper(feed_url=encode_unicode(config.get(constants.CONFIG_FEED_URL)),
                       working_directory=repo.working_dir,
                       max_speed=max_speed, num_threads=num_threads,
                       ssl_client_cert=config.get(constants.CONFIG_SSL_CLIENT_CERT),
                       ssl_ca_cert=config.get(constants.CONFIG_SSL_CA_CERT),
                       proxy_url=config.get(constants.CONFIG_PROXY_URL),
                       proxy_port=config.get(constants.CONFIG_PROXY_PORT),
                       proxy_user=config.get(constants.CONFIG_PROXY_USER),
                       proxy_password=config.get(constants.CONFIG_PROXY_PASSWORD))

    manifest = bumper.manifest
    missing_isos = _filter_missing_isos(sync_conduit, manifest)
    bumper.download_files(missing_isos)

    # Move the downloaded stuff and junk to the permanent location
    _create_units(sync_conduit, missing_isos)

    # Report that we are finished
    progress_report.metadata_state = STATE_COMPLETE
    progress_report.modules_state = STATE_COMPLETE
    report = progress_report.build_final_report()
    return report


def _filter_missing_isos(sync_conduit, manifest):
    def _unit_key_str(unit_key_dict):
        return '%s-%s-%s'%(unit_key_dict['name'], unit_key_dict['checksum_type'],
                           unit_key_dict['checksum'])

    available_units_by_key = dict([(_unit_key_str(u), u) for u in manifest])

    module_criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_ISO])
    existing_isos = sync_conduit.get_units(criteria=module_criteria)
    existing_iso_keys = set([_unit_key_str(m.unit_key) for m in existing_isos])
    available_iso_keys = set([_unit_key_str(u) for u in manifest])

    missing_iso_keys = list(available_iso_keys - existing_iso_keys)
    missing_isos = [available_units_by_key[k] for k in missing_iso_keys]
    return missing_isos


# TODO: Handle Grinder callback. We can probaby make this a function that returns a function so that
#       we can pass the sync_conduit for reporting.
def grinder_progress_callback(progress_report):
    # These are the attributes that the progress_report should have
    # self.items_total = itemTotal    # Total number of items
    # self.items_left = itemLeft      # Number of items left to process
    # self.size_total = sizeTotal     # Total number of bytes 
    # self.size_left = sizeLeft       # Bytes left to process
    # self.item_name = itemName       # Name of last item worked on
    # self.status = status            # Status Message
    # self.item_type = itemType       # Type of item fetched
    # self.num_error = 0              # Number of Errors
    # self.num_success = 0            # Number of Successes
    # self.num_download = 0           # Number of actual downloads
    # self.details = {}               # Details about specific file types
    # self.error_details = []         # Details about specific errors that were observed
                                      # List of tuples. Tuple format [0] = item info,
                                      # [1] = exception details
    # self.step = None
    pass


def _create_units(sync_conduit, new_units):
    for iso in new_units:
        unit_key = {'name': iso['name'], 'checksum_type': iso['checksum_type'],
                    'checksum': iso['checksum']}
        metadata = {'size': iso['size']}
        relative_path = os.path.join(unit_key['checksum_type'], unit_key['checksum'],
                                     unit_key['name'])
        unit = sync_conduit.init_unit(ids.TYPE_ID_ISO, unit_key, metadata, relative_path)
        # Copy the unit to the storage_path
        temporary_file_location = iso['path']
        permanent_file_location = unit.storage_path
        # We only need to create the permanent location if it isn't already there.
        if not os.path.exists(os.path.dirname(permanent_file_location)):
            try:
                # Create the destination directory
                os.makedirs(os.path.dirname(permanent_file_location))
            except OSError, e:
                # If we encounter a race where something else creates this directory between our
                # check for existence and now, we can move on because the path now exists. Otherwise
                # we need to raise this mammajamma
                if e.errno != errno.EEXIST:
                    raise
        shutil.move(temporary_file_location, permanent_file_location)
        unit = sync_conduit.save_unit(unit)
