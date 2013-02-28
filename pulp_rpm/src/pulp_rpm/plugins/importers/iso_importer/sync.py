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
from cStringIO import StringIO
from gettext import gettext as _
from urlparse import urljoin
import csv
import hashlib
import logging
import os

from pulp_rpm.common import constants, ids
from pulp_rpm.common.constants import STATE_COMPLETE, STATE_RUNNING, STATE_FAILED
from pulp_rpm.common.progress import SyncProgressReport

from pulp.common.download import factory, listener, request
from pulp.common.download.config import DownloaderConfig
from pulp.common.util import encode_unicode
from pulp.plugins.conduits.mixins import UnitAssociationCriteria


logger = logging.getLogger(__name__)
# How many bytes we want to read into RAM at a time when validating a download checksum
VALIDATION_CHUNK_SIZE = 32 * 1024 * 1024


class ISOSyncRun(listener.DownloadEventListener):
    """
    This class maintains state for a single repository sync (do not reuse it). We need to keep the state so
    that we can cancel a sync that is in progress. It subclasses DownloadEventListener so it can pass itself
    to the downloader library and receive the callbacks when downloads are complete.
    """
    def __init__(self, sync_conduit, config):
        self.sync_conduit = sync_conduit
        self._remove_missing_units = config.get(constants.CONFIG_REMOVE_MISSING_UNITS, default=False)
        self._repo_url = encode_unicode(config.get(constants.CONFIG_FEED_URL))
        self._validate_downloads = config.get(constants.CONFIG_VALIDATE_DOWNLOADS, default=True)

        # Cast our config parameters to the correct types and use them to build a Downloader
        max_speed = config.get(constants.CONFIG_MAX_SPEED)
        if max_speed is not None:
            max_speed = float(max_speed)
        num_threads = config.get(constants.CONFIG_NUM_THREADS)
        if num_threads is not None:
            num_threads = int(num_threads)
        else:
            num_threads = constants.DEFAULT_NUM_THREADS
        downloader_config = {
            'max_speed': max_speed, 'num_threads': num_threads,
            'ssl_client_cert': config.get(constants.CONFIG_SSL_CLIENT_CERT),
            'ssl_client_key': config.get(constants.CONFIG_SSL_CLIENT_KEY),
            'ssl_ca_cert': config.get(constants.CONFIG_SSL_CA_CERT), 'ssl_verify_host': 1,
            'ssl_verify_peer': 1, 'proxy_url': config.get(constants.CONFIG_PROXY_URL),
            'proxy_port': config.get(constants.CONFIG_PROXY_PORT),
            'proxy_user': config.get(constants.CONFIG_PROXY_USER),
            'proxy_password': config.get(constants.CONFIG_PROXY_PASSWORD)}
        downloader_config = DownloaderConfig(protocol='https', **downloader_config)

        # We will pass self as the event_listener, so that we can receive the callbacks in this class
        self.downloader = factory.get_downloader(downloader_config, self)
        self.progress_report = SyncProgressReport(sync_conduit)

    def cancel_sync(self):
        """
        This method will cancel a sync that is in progress.
        """
        # We used to support sync cancellation, but the current downloader implementation does not support it
        # and so for now we will just pass
        pass

    def download_failed(self, report):
        """
        This is the callback that we will get from the downloader library when any individual download fails.
        """
        # If we have a download failure during the manifest phase, we should set the report to failed for that
        # phase.
        if self.progress_report.manifest_state == STATE_RUNNING:
            self.progress_report.manifest_state = STATE_FAILED
        elif self.progress_report.isos_state == STATE_RUNNING:
            iso = self._url_iso_map[report.url]
            self.progress_report.add_failed_iso(iso, report.error_report)
            del self._url_iso_map[report.url]
        self.progress_report.update_progress()

    def download_progress(self, report):
        """
        We will get notified from time to time about some bytes we've downloaded. We can update our progress
        report with this information so the client can see the progress.

        :param report: The report of the file we are downloading
        :type  report: pulp.common.download.report.DownloadReport
        """
        if self.progress_report.isos_state == STATE_RUNNING:
            iso = self._url_iso_map[report.url]
            additional_bytes_downloaded = report.bytes_downloaded - iso['bytes_downloaded']
            self.progress_report.isos_finished_bytes += additional_bytes_downloaded
            iso['bytes_downloaded'] = report.bytes_downloaded
            self.progress_report.update_progress()

    def download_succeeded(self, report):
        """
        This is the callback that we will get from the downloader library when it succeeds in downloading a
        file. This method will check to see if we are in the ISO downloading stage, and if we are, it will add
        the new ISO to the database.

        :param report: The report of the file we downloaded
        :type  report: pulp.common.download.report.DownloadReport
        """
        # If we are in the isos stage, then this must be one of our ISOs.
        if self.progress_report.isos_state == STATE_RUNNING:
            # This will update our bytes downloaded
            self.download_progress(report)
            iso = self._url_iso_map[report.url]
            try:
                if self._validate_downloads:
                    self._validate_download(iso)
                self.sync_conduit.save_unit(iso['unit'])
                # We can drop this ISO from the url --> ISO map
                self.progress_report.isos_finished_count += 1
                self.progress_report.update_progress()
                del self._url_iso_map[report.url]
            except ValueError:
                self.download_failed(report)

    def perform_sync(self):
        """
        Perform the sync operation accoring to the config, and return a report.
        The sync progress will be reported through the sync_conduit.

        :return:             The sync report
        :rtype:              pulp.plugins.model.SyncReport
        """
        # Get the manifest and download the ISOs that we are missing
        self.progress_report.manifest_state = STATE_RUNNING
        self.progress_report.update_progress()
        manifest = self._download_manifest()
        self.progress_report.manifest_state = STATE_COMPLETE

        # Go get them filez
        self.progress_report.isos_state = STATE_RUNNING
        self.progress_report.update_progress()
        local_missing_isos, remote_missing_isos = self._filter_missing_isos(manifest)
        self._download_isos(local_missing_isos)
        if self._remove_missing_units:
            self._remove_units(remote_missing_isos)

        # Report that we are finished
        self.progress_report.isos_state = STATE_COMPLETE
        self.progress_report.update_progress()
        report = self.progress_report.build_final_report()
        return report

    def _download_isos(self, manifest):
        """
        Makes the calls to retrieve the ISOs from the manifest, storing them on disk and recording them in the
        Pulp database.

        :param manifest: The manifest containing a list of ISOs we want to download. It is a list of
                         dictionaries with at least the following keys: name, checksum, size, and url.
        :type  manifest: list
        """
        self.progress_report.isos_total_bytes = 0
        self.progress_report.isos_total_count = len(manifest)
        # For each ISO in the manifest, we need to determine a relative path where we want it to be stored,
        # and initialize the Unit that will represent it
        for iso in manifest:
            unit_key = {'name': iso['name'], 'size': iso['size'], 'checksum': iso['checksum']}
            metadata = {}
            relative_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']), unit_key['name'])
            unit = self.sync_conduit.init_unit(ids.TYPE_ID_ISO, unit_key, metadata, relative_path)
            iso['destination'] = unit.storage_path
            iso['unit'] = unit
            iso['bytes_downloaded'] = 0
            # Set the total bytes onto the report
            self.progress_report.isos_total_bytes += iso['size']
        self.progress_report.update_progress()
        # We need to build a list of DownloadRequests
        download_requests = [request.DownloadRequest(iso['url'], iso['destination']) for iso in manifest]
        # Let's build an index from URL to the manifest unit dictionary, so that we can access data like the
        # name, checksum, and size as we process completed downloads
        self._url_iso_map = dict([(iso['url'], iso) for iso in manifest])
        self.downloader.download(download_requests)

    def _download_manifest(self):
        """
        Download the manifest file, and process it to return a list of the available Units. The available
        units will be a list of dictionaries that describe the available ISOs, with these keys: name,
        checksum, size, and url.

        :return:     list of available ISOs
        :rtype:      list
        """
        manifest_url = urljoin(self._repo_url, constants.ISO_MANIFEST_FILENAME)
        # I probably should have called this manifest destination, but I couldn't help myself
        manifest_destiny = StringIO()
        manifest_request = request.DownloadRequest(manifest_url, manifest_destiny)
        self.downloader.download([manifest_request])
        # We can inspect the report status to see if we had an error when retrieving the manifest.
        if self.progress_report.manifest_state == STATE_FAILED:
            raise IOError(_("Could not retrieve %(url)s") % {'url': manifest_url})

        # Now let's process the manifest and return a list of resources that we'd like to download
        manifest_destiny.seek(0)
        manifest_csv = csv.reader(manifest_destiny)
        manifest = []
        for unit in manifest_csv:
            name, checksum, size = unit
            resource = {'name': name, 'checksum': checksum, 'size': int(size),
                        'url': urljoin(self._repo_url, name)}
            manifest.append(resource)
        return manifest

    def _filter_missing_isos(self, manifest):
        """
        Use the sync_conduit and the manifest to determine which ISOs are at the feed_url
        that are not in our local store, as well as which ISOs are in our local store that are not available
        at the feed_url. Return a 2-tuple with this information. The first element of the tuple will be a
        subset of the given manifest that represents the missing ISOs. The second element will be a list of
        units that represent the ISOs we have in our local store that weren't found at the feed_url. The
        manifest is a list of dictionaries that must contain at a minimum the following keys: name, checksum,
        size.

        :param manifest:     A list of dictionaries that describe the ISOs that are available at the
                             feed_url that we are synchronizing with
        :type  manifest:     list
        :return:             A 2-tuple. The first element of the tuple is a list of dictionaries that describe
                             the ISOs that we should retrieve from the feed_url. These dictionaries are in the
                             same format as they were in the manifest. The second element of the tuple is a
                             list of units that represent the ISOs that we have in our local repo that were
                             not found in the remote repo.
        :rtype:              tuple
        """
        def _unit_key_str(unit_key_dict):
            return '%s-%s-%s' % (unit_key_dict['name'], unit_key_dict['checksum'],
                                 unit_key_dict['size'])

        module_criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_ISO])
        existing_units = self.sync_conduit.get_units(criteria=module_criteria)

        available_isos_by_key = dict([(_unit_key_str(iso), iso) for iso in manifest])
        existing_units_by_key = dict([(_unit_key_str(unit.unit_key), unit) for unit in existing_units])

        existing_unit_keys = set([_unit_key_str(unit.unit_key) for unit in existing_units])
        available_iso_keys = set([_unit_key_str(iso) for iso in manifest])

        local_missing_iso_keys = list(available_iso_keys - existing_unit_keys)
        local_missing_isos = [available_isos_by_key[k] for k in local_missing_iso_keys]
        remote_missing_unit_keys = list(existing_unit_keys - available_iso_keys)
        remote_missing_units = [existing_units_by_key[k] for k in remote_missing_unit_keys]

        return local_missing_isos, remote_missing_units

    def _remove_units(self, units):
        """
        Use the sync_conduit's remove_unit call for each unit in units.

        :param units: List of pulp.plugins.model.Units that we want to remove from the repository
        :type  units: list
        """
        for unit in units:
            self.sync_conduit.remove_unit(unit)

    def _validate_download(self, iso):
        """
        Validate the size and the checksum of the given downloaded iso. iso should be a dictionary with at
        least these keys: name, checksum, size, and destination.

        :param iso: A dictionary describing the ISO file we want to validate
        :type  iso: dict
        """
        with open(iso['destination']) as destination_file:
            # Validate the size, if we know what it should be
            if 'size' in iso:
                # seek to the end to find the file size with tell()
                destination_file.seek(0, 2)
                size = destination_file.tell()
                if size != iso['size']:
                    raise ValueError(_('Downloading <%(name)s> failed validation. '
                        'The manifest specified that the file should be %(expected)s bytes, but '
                        'the downloaded file is %(found)s bytes.') % {'name': iso['name'],
                            'expected': iso['size'], 'found': size})

            # Validate the checksum, if we know what it should be
            if 'checksum' in iso:
                destination_file.seek(0)
                hasher = hashlib.sha256()
                bits = destination_file.read(VALIDATION_CHUNK_SIZE)
                while bits:
                    hasher.update(bits)
                    bits = destination_file.read(VALIDATION_CHUNK_SIZE)
                # Verify that, son!
                if hasher.hexdigest() != iso['checksum']:
                    raise ValueError(
                        _('Downloading <%(name)s> failed checksum validation. The manifest '
                          'specified the checksum to be %(c)s, but it was %(f)s.') % {
                            'name': iso['name'], 'c': iso['checksum'],
                            'f': hasher.hexdigest()})
