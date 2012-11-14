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

from grinder.FileFetch import FileGrinder
import pulp.server.util

from pulp_rpm.common import ids
from pulp_rpm.common.constants import STATE_RUNNING, STATE_COMPLETE
from pulp_rpm.common.sync_progress import SyncProgressReport
from pulp_rpm.plugins.importers.iso_importer import configuration


logger = logging.getLogger(__name__)


# TODO: Delete Units that we have that weren't found in the repo
def perform_sync(repo, sync_conduit, config):
    """
    Perform the sync operation accoring to the config for the given repo, and return a report. The
    sync progress will be reported through the sync_conduit.

    :rtype: pulp.plugins.model.SyncReport
    """
    progress_report = SyncProgressReport(sync_conduit)
    progress_report.metadata_state = STATE_RUNNING
    progress_report.modules_state = STATE_RUNNING

    # Set up the Grinder and get stuff. Unfortunately, it seems that Grinder insists on downloading
    # all the files on every sync, unless there are ways to use Grinder that I haven't found yet.
    # After all, I am not very familiar with Grinder...
    grinder = FileGrinder('', config.get('feed_url'),
                          int(config.get('num_threads') or
                              configuration.CONFIG_DEFAULTS['num_threads']),
                          cacert=config.get('ssl_ca_cert'), clicert=config.get('ssl_client_cert'),
                          proxy_url=config.get('proxy_url'), proxy_port=config.get('proxy_port'),
                          proxy_user=config.get('proxy_user'),
                          proxy_pass=config.get('proxy_password'),
                          max_speed=config.get('max_speed'))
    store_path = os.path.join(repo.working_dir, 'pulp_test_yo')
    report = grinder.fetch(store_path, callback=grinder_progress_callback)
    # Copy the stuff in there to the permanent location
    _create_units(sync_conduit, grinder.downloadinfo)

    # Report that we are finished
    progress_report.metadata_state = STATE_COMPLETE
    progress_report.modules_state = STATE_COMPLETE
    report = progress_report.build_final_report()
    return report


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


def _create_units(sync_conduit, grinder_downloadinfo):
    for iso in grinder_downloadinfo:
        logger.debug('iso: %s'%iso)
        unit_key = {'name': iso['fileName'], 'checksum_type': iso['checksumtype'],
                    'checksum': iso['checksum']}
        metadata = {}
        relative_path = os.path.join(unit_key['checksum_type'], unit_key['checksum'])
        unit = sync_conduit.init_unit(ids.TYPE_ID_ISO, unit_key, metadata, relative_path)
        # Copy the unit to the storage_path
        logger.debug('storage_path: %s'%unit.storage_path)
        temporary_file_location = os.path.join(iso['savepath'], unit_key['name'])
        permanent_file_location = os.path.join(unit.storage_path, unit_key['name'])
        # We only need to copy the file to the permanent location if it isn't already there.
        if not os.path.exists(permanent_file_location):
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
