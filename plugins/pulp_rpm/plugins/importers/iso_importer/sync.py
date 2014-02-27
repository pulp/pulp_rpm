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
import logging

from nectar import listener, request
from nectar.config import DownloaderConfig
from nectar.downloaders.threaded import HTTPThreadedDownloader
from nectar.downloaders.local import LocalFileDownloader
from pulp.common.plugins import importer_constants
from pulp.common.util import encode_unicode
from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp_rpm.common import constants, ids, models
from pulp_rpm.common.progress import SyncProgressReport


logger = logging.getLogger(__name__)


class ISOSyncRun(listener.DownloadEventListener):
    """
    This class maintains state for a single repository sync (do not reuse it). We need to keep the state so
    that we can cancel a sync that is in progress. It subclasses DownloadEventListener so it can pass itself
    to the downloader library and receive the callbacks when downloads are complete.
    """
    def __init__(self, sync_conduit, config):
        self.sync_conduit = sync_conduit
        self._remove_missing_units = config.get(importer_constants.KEY_UNITS_REMOVE_MISSING,
                                                default=constants.CONFIG_UNITS_REMOVE_MISSING_DEFAULT)
        self._validate_downloads = config.get(importer_constants.KEY_VALIDATE,
                                              default=constants.CONFIG_VALIDATE_DEFAULT)
        self._repo_url = encode_unicode(config.get(importer_constants.KEY_FEED))
        # The _repo_url must end in a trailing slash, because we will use urljoin to determine the path to
        # PULP_MANIFEST later
        if self._repo_url[-1] != '/':
            self._repo_url = self._repo_url + '/'

        # Cast our config parameters to the correct types and use them to build a Downloader
        max_speed = config.get(importer_constants.KEY_MAX_SPEED)
        if max_speed is not None:
            max_speed = float(max_speed)
        max_downloads = config.get(importer_constants.KEY_MAX_DOWNLOADS)
        if max_downloads is not None:
            max_downloads = int(max_downloads)
        else:
            max_downloads = constants.CONFIG_MAX_DOWNLOADS_DEFAULT
        ssl_validation = config.get_boolean(importer_constants.KEY_SSL_VALIDATION)
        ssl_validation = ssl_validation if ssl_validation is not None else constants.CONFIG_VALIDATE_DEFAULT
        downloader_config = {
            'max_speed': max_speed,
            'max_concurrent': max_downloads,
            'ssl_client_cert': config.get(importer_constants.KEY_SSL_CLIENT_CERT),
            'ssl_client_key': config.get(importer_constants.KEY_SSL_CLIENT_KEY),
            'ssl_ca_cert': config.get(importer_constants.KEY_SSL_CA_CERT),
            'ssl_validation': ssl_validation,
            'proxy_url': config.get(importer_constants.KEY_PROXY_HOST),
            'proxy_port': config.get(importer_constants.KEY_PROXY_PORT),
            'proxy_username': config.get(importer_constants.KEY_PROXY_USER),
            'proxy_password': config.get(importer_constants.KEY_PROXY_PASS)}
        downloader_config = DownloaderConfig(**downloader_config)

        # We will pass self as the event_listener, so that we can receive the callbacks in this class
        if self._repo_url.lower().startswith('file'):
            self.downloader = LocalFileDownloader(downloader_config, self)
        else:
            self.downloader = HTTPThreadedDownloader(downloader_config, self)
        self.progress_report = SyncProgressReport(sync_conduit)

    def cancel_sync(self):
        """
        This method will cancel a sync that is in progress.
        """
        # We used to support sync cancellation, but the current downloader implementation does not support it
        # and so for now we will just pass
        self.progress_report.state = self.progress_report.STATE_CANCELLED
        self.downloader.cancel()

    def download_failed(self, report):
        """
        This is the callback that we will get from the downloader library when any individual
        download fails.
        """
        # If we have a download failure during the manifest phase, we should set the report to
        # failed for that phase.
        if self.progress_report.state == self.progress_report.STATE_MANIFEST_IN_PROGRESS:
            self.progress_report.state = self.progress_report.STATE_MANIFEST_FAILED
            self.progress_report.error_message = report.error_report
        elif self.progress_report.state == self.progress_report.STATE_ISOS_IN_PROGRESS:
            iso = report.data
            self.progress_report.add_failed_iso(iso, report.error_report)
        self.progress_report.update_progress()

    def download_progress(self, report):
        """
        We will get notified from time to time about some bytes we've downloaded. We can update our progress
        report with this information so the client can see the progress.

        :param report: The report of the file we are downloading
        :type  report: nectar.report.DownloadReport
        """
        if self.progress_report.state == self.progress_report.STATE_ISOS_IN_PROGRESS:
            iso = report.data
            additional_bytes_downloaded = report.bytes_downloaded - iso.bytes_downloaded
            self.progress_report.finished_bytes += additional_bytes_downloaded
            iso.bytes_downloaded = report.bytes_downloaded
            self.progress_report.update_progress()

    def download_succeeded(self, report):
        """
        This is the callback that we will get from the downloader library when it succeeds in downloading a
        file. This method will check to see if we are in the ISO downloading stage, and if we are, it will add
        the new ISO to the database.

        :param report: The report of the file we downloaded
        :type  report: nectar.report.DownloadReport
        """
        # If we are in the isos stage, then this must be one of our ISOs.
        if self.progress_report.state == self.progress_report.STATE_ISOS_IN_PROGRESS:
            # This will update our bytes downloaded
            self.download_progress(report)
            iso = report.data
            try:
                if self._validate_downloads:
                    iso.validate()
                iso.save_unit(self.sync_conduit)
                # We can drop this ISO from the url --> ISO map
                self.progress_report.num_isos_finished += 1
                self.progress_report.update_progress()
            except ValueError:
                self.download_failed(report)

    def perform_sync(self):
        """
        Perform the sync operation according to the config, and return a report.
        The sync progress will be reported through the sync_conduit.

        :return:             The sync report
        :rtype:              pulp.plugins.model.SyncReport
        """
        # Get the manifest and download the ISOs that we are missing
        self.progress_report.state = self.progress_report.STATE_MANIFEST_IN_PROGRESS
        try:
            manifest = self._download_manifest()
        except (IOError, ValueError):
            # The IOError will happen if the file can't be retrieved at all, and the ValueError will
            # happen if the PULP_MANIFEST file isn't in the expected format.
            return self.progress_report.build_final_report()

        # Go get them filez
        self.progress_report.state = self.progress_report.STATE_ISOS_IN_PROGRESS
        local_missing_isos, remote_missing_isos = self._filter_missing_isos(manifest)
        self._download_isos(local_missing_isos)
        if self._remove_missing_units:
            self._remove_units(remote_missing_isos)

        # Report that we are finished. Note that setting the
        # state to STATE_ISOS_COMPLETE will automatically set the state to STATE_ISOS_FAILED if the
        # progress report has collected any errors. See the progress_report's _set_state() method
        # for the implementation of this logic.
        self.progress_report.state = self.progress_report.STATE_COMPLETE
        report = self.progress_report.build_final_report()
        return report

    def _download_isos(self, manifest):
        """
        Makes the calls to retrieve the ISOs from the manifest, storing them on disk and recording them in the
        Pulp database.

        :param manifest: The manifest containing a list of ISOs we want to download.
        :type  manifest: list
        """
        self.progress_report.total_bytes = 0
        self.progress_report.num_isos = len(manifest)
        # For each ISO in the manifest, we need to determine a relative path where we want it to be stored,
        # and initialize the Unit that will represent it
        for iso in manifest:
            iso.init_unit(self.sync_conduit)
            iso.bytes_downloaded = 0
            # Set the total bytes onto the report
            self.progress_report.total_bytes += iso.size
        self.progress_report.update_progress()
        # We need to build a list of DownloadRequests
        download_requests = [request.DownloadRequest(iso.url, iso.storage_path, iso) for iso in manifest]
        self.downloader.download(download_requests)

    def _download_manifest(self):
        """
        Download the manifest file, and process it to return an ISOManifest.

        :return: manifest of available ISOs
        :rtype:  pulp_rpm.common.models.ISOManifest
        """
        manifest_url = urljoin(self._repo_url, models.ISOManifest.FILENAME)
        # I probably should have called this manifest destination, but I couldn't help myself
        manifest_destiny = StringIO()
        manifest_request = request.DownloadRequest(manifest_url, manifest_destiny)
        self.downloader.download([manifest_request])
        # We can inspect the report status to see if we had an error when retrieving the manifest.
        if self.progress_report.state == self.progress_report.STATE_MANIFEST_FAILED:
            raise IOError(_("Could not retrieve %(url)s") % {'url': manifest_url})

        manifest_destiny.seek(0)
        try:
            manifest = models.ISOManifest(manifest_destiny, self._repo_url)
        except ValueError, e:
            self.progress_report.error_message = _('The PULP_MANIFEST file was not in the ' +\
                                                   'expected format.')
            self.progress_report.state = self.progress_report.STATE_MANIFEST_FAILED
            raise ValueError(self.progress_report.error_message)

        return manifest

    def _filter_missing_isos(self, manifest):
        """
        Use the sync_conduit and the manifest to determine which ISOs are at the feed_url
        that are not in our local store, as well as which ISOs are in our local store that are not available
        at the feed_url. Return a 2-tuple with this information. The first element of the tuple will be a
        list of ISO objects that represent the missing ISOs. The second element will be a list of
        Units that represent the ISOs we have in our local store that weren't found at the feed_url.

        :param manifest: An ISOManifest describing the ISOs that are available at the
                         feed_url that we are synchronizing with
        :type  manifest: pulp_rpm.common.models.ISOManifest
        :return:         A 2-tuple. The first element of the tuple is a list of ISOs that we should retrieve
                         from the feed_url. The second element of the tuple is a list of Units that
                         represent the ISOs that we have in our local repo that were not found in the remote
                         repo.
        :rtype:          tuple
        """
        def _unit_key_str(iso):
            """
            Return a simple string representation of the unit key of the ISO.

            :param iso: The ISO for which we want a unit key string representation
            :type  iso: pulp_rpm.common.models.ISO
            """
            return '%s-%s-%s' % (iso.name, iso.checksum, iso.size)

        module_criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_ISO])
        existing_units = self.sync_conduit.get_units(criteria=module_criteria)

        available_isos_by_key = dict([(_unit_key_str(iso), iso) for iso in manifest])
        existing_units_by_key = dict([(_unit_key_str(models.ISO.from_unit(unit)), unit) \
                                      for unit in existing_units])

        existing_unit_keys = set([_unit_key_str(models.ISO.from_unit(unit)) for unit in existing_units])
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
