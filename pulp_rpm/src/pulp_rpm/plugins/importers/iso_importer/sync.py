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

# TODO: Reproduce folder structures that may have been found on the server
# TODO: optionally delete Units that we have that weren't found in the repo
# TODO: optionally don't check the checksum and size
# TODO: Error handling
class ISOSyncRun(object):
    """
    This class maintains state for a single repository sync. We need to keep the state so that we
    can cancel a sync that is in progress.
    """
    def cancel_sync(self):
        """
        This method will cancel a sync that is in progress.
        """
        self.bumper.download_canceled = True

    def perform_sync(self, repo, sync_conduit, config):
        """
        Perform the sync operation accoring to the config for the given repo, and return a report.
        The sync progress will be reported through the sync_conduit.

        :param sync_conduit: The sync_conduit that gives us access to the local repository
        :type  sync_conduit: pulp.server.conduits.repo_sync.RepoSyncConduit
        :param config:       The configuration for the importer
        :type  config:       pulp.server.plugins.config.PluginCallConfiguration
        :return:             The sync report
        :rtype:              pulp.plugins.model.SyncReport
        """
        # Build the progress report and set it to the running state
        progress_report = SyncProgressReport(sync_conduit)
        progress_report.metadata_state = STATE_RUNNING
        progress_report.modules_state = STATE_RUNNING

        # Cast our config parameters to the correct types and use them to build an ISOBumper
        max_speed = config.get(constants.CONFIG_MAX_SPEED)
        if max_speed is not None:
            max_speed = float(max_speed)
        num_threads = config.get(constants.CONFIG_NUM_THREADS)
        if num_threads is not None:
            num_threads = int(num_threads)
        else:
            num_threads = constants.DEFAULT_NUM_THREADS
        self.bumper = ISOBumper(
                           repo_url=encode_unicode(config.get(constants.CONFIG_FEED_URL)),
                           working_path=repo.working_dir,
                           max_speed=max_speed, num_threads=num_threads,
                           ssl_client_cert=config.get(constants.CONFIG_SSL_CLIENT_CERT),
                           ssl_client_key=config.get(constants.CONFIG_SSL_CLIENT_KEY),
                           ssl_ca_cert=config.get(constants.CONFIG_SSL_CA_CERT),
                           proxy_url=config.get(constants.CONFIG_PROXY_URL),
                           proxy_port=config.get(constants.CONFIG_PROXY_PORT),
                           proxy_user=config.get(constants.CONFIG_PROXY_USER),
                           proxy_password=config.get(constants.CONFIG_PROXY_PASSWORD))

        # Get the manifest and download the ISOs that we are missing
        manifest = self.bumper.get_manifest()
        missing_isos = self._filter_missing_isos(sync_conduit, manifest)
        # TODO: Consider processing each ISO completely instead of downloading them all and then
        # _create_units
        new_isos = self.bumper.download_resources(missing_isos)

        # Move the downloaded stuff and junk to the permanent location
        self._create_units(sync_conduit, new_isos)

        # Report that we are finished
        progress_report.metadata_state = STATE_COMPLETE
        progress_report.modules_state = STATE_COMPLETE
        report = progress_report.build_final_report()
        return report


    def _filter_missing_isos(self, sync_conduit, manifest):
        """
        Use the sync_conduit and the ISOBumper manifest to determine which ISOs are at the feed_url
        that are not in our local store. Return a subset of the given manifest that represents the
        missing ISOs. The manifest format is described in the docblock for
        pulp_rpm.plugins.importers.iso_importer.bumper.ISOBumper.manifest.

        :param sync_conduit: The sync_conduit that gives us access to the local repository
        :type  sync_conduit: pulp.server.conduits.repo_sync.RepoSyncConduit
        :param manifest:     A list of dictionaries that describe the ISOs that are available at the
                             feed_url that we are syncing with
        :type  manifest:     list
        :return:             A list of dictionaries that describe the ISOs that we should retrieve
                             from the feed_url. These dictionaries are in the same format as they
                             were in the manifest.
        :rtype:              list
        """
        def _unit_key_str(unit_key_dict):
            return '%s-%s-%s'%(unit_key_dict['name'], unit_key_dict['checksum'],
                               unit_key_dict['size'])

        available_units_by_key = dict([(_unit_key_str(u), u) for u in manifest])

        module_criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_ISO])
        existing_isos = sync_conduit.get_units(criteria=module_criteria)
        existing_iso_keys = set([_unit_key_str(m.unit_key) for m in existing_isos])
        available_iso_keys = set([_unit_key_str(u) for u in manifest])

        missing_iso_keys = list(available_iso_keys - existing_iso_keys)
        missing_isos = [available_units_by_key[k] for k in missing_iso_keys]
        return missing_isos


    def _create_units(self, sync_conduit, new_isos):
        """
        For each ISO specified in new_isos, create a new Pulp Unit and move the file from its
        temporary storage location to the storage location specified by the Unit. new_isos is a list
        of dictionaries that describe the isos that have been downloaded, and is the same format as
        the return value from
        pulp_rpm.plugins.importers.iso_importer.bumper.ISOBumper.download_resources.

        :param sync_conduit: The sync_conduit that gives us access to the local repository
        :type  sync_conduit: pulp.server.conduits.repo_sync.RepoSyncConduit
        :param new_isos:     A list of dictionaries describing the newly downloaded ISOs.
        :type  new_isos:     list
        """
        for iso in new_isos:
            unit_key = {'name': iso['name'], 'size': iso['size'], 'checksum': iso['checksum']}
            metadata = {}
            # TODO: Put name first
            relative_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']))
            unit = sync_conduit.init_unit(ids.TYPE_ID_ISO, unit_key, metadata, relative_path)
            # Move the unit to the storage_path
            temporary_file_location = iso['destination']
            permanent_file_location = unit.storage_path
            # We only need to create the permanent location if it isn't already there.
            shutil.move(temporary_file_location, permanent_file_location)
            unit = sync_conduit.save_unit(unit)
