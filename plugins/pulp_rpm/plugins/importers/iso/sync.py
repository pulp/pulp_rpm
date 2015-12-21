from cStringIO import StringIO
from gettext import gettext as _
from urlparse import urljoin
import logging
import os
import tempfile

from nectar import listener, request
from nectar.config import DownloaderConfig
from nectar.downloaders.threaded import HTTPThreadedDownloader
from nectar.downloaders.local import LocalFileDownloader

from pulp.common.plugins import importer_constants
from pulp.common.util import encode_unicode
from pulp.server.controllers import repository as repo_controller
from pulp.server.db.model import LazyCatalogEntry
from pulp.server.managers.repo import _common as common_utils

from pulp_rpm.common import constants
from pulp_rpm.common.progress import SyncProgressReport
from pulp_rpm.plugins.db import models


_logger = logging.getLogger(__name__)


class ISOSyncRun(listener.DownloadEventListener):
    """
    This class maintains state for a single repository sync (do not reuse it). We need to keep
    the state so that we can cancel a sync that is in progress. It subclasses DownloadEventListener
    so it can pass itself to the downloader library and receive the callbacks when downloads are
    complete.
    """

    def __init__(self, sync_conduit, config):
        """
        Initialize an ISOSyncRun.

        :param sync_conduit: the sync conduit to use for this sync run.
        :type  sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config:       plugin configuration
        :type  config:       pulp.plugins.config.PluginCallConfiguration
        """
        self.sync_conduit = sync_conduit
        self.config = config
        self._remove_missing_units = config.get(
            importer_constants.KEY_UNITS_REMOVE_MISSING,
            default=constants.CONFIG_UNITS_REMOVE_MISSING_DEFAULT)
        self._validate_downloads = config.get(importer_constants.KEY_VALIDATE,
                                              default=constants.CONFIG_VALIDATE_DEFAULT)
        self._repo_url = encode_unicode(config.get(importer_constants.KEY_FEED))
        # The _repo_url must end in a trailing slash, because we will use urljoin to determine
        # the path to
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
        ssl_validation = ssl_validation if ssl_validation is not None else \
            constants.CONFIG_VALIDATE_DEFAULT
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

        # We will pass self as the event_listener, so that we can receive the callbacks in this
        # class
        if self._repo_url.lower().startswith('file'):
            self.downloader = LocalFileDownloader(downloader_config, self)
        else:
            self.downloader = HTTPThreadedDownloader(downloader_config, self)
        self.progress_report = SyncProgressReport(sync_conduit)

    @property
    def download_deferred(self):
        """
        Test the download policy to determine if downloading is deferred.

        :return: True if deferred.
        :rtype: bool
        """
        policy = self.config.get(
            importer_constants.DOWNLOAD_POLICY,
            importer_constants.DOWNLOAD_IMMEDIATE)
        return policy != importer_constants.DOWNLOAD_IMMEDIATE

    def cancel_sync(self):
        """
        This method will cancel a sync that is in progress.
        """
        # We used to support sync cancellation, but the current downloader implementation does
        # not support it
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
        msg = _('Failed to download %(url)s: %(error_msg)s.')
        msg = msg % {'url': report.url, 'error_msg': report.error_msg}
        _logger.error(msg)
        if self.progress_report.state == self.progress_report.STATE_MANIFEST_IN_PROGRESS:
            self.progress_report.state = self.progress_report.STATE_MANIFEST_FAILED
            self.progress_report.error_message = report.error_report
        elif self.progress_report.state == self.progress_report.STATE_ISOS_IN_PROGRESS:
            iso = report.data
            self.progress_report.add_failed_iso(iso, report.error_report)
        self.progress_report.update_progress()

    def download_progress(self, report):
        """
        We will get notified from time to time about some bytes we've downloaded. We can update
        our progress
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
        This is the callback that we will get from the downloader library when it succeeds in
        downloading a file. This method will check to see if we are in the ISO downloading stage,
        and if we are, it will add the new ISO to the database.

        :param report: The report of the file we downloaded
        :type  report: nectar.report.DownloadReport
        """
        # If we are in the isos stage, then this must be one of our ISOs.
        if self.progress_report.state == self.progress_report.STATE_ISOS_IN_PROGRESS:
            # This will update our bytes downloaded
            self.download_progress(report)
            iso = report.data
            iso.set_storage_path(os.path.basename(report.destination))
            try:
                if self._validate_downloads:
                    iso.validate_iso(report.destination)
                iso.save()
                iso.import_content(report.destination)
                repo_controller.associate_single_unit(self.sync_conduit.repo, iso)

                # We can drop this ISO from the url --> ISO map
                self.progress_report.num_isos_finished += 1
                self.progress_report.update_progress()
            except ValueError:
                self.download_failed(report)

    def add_catalog_entries(self, units):
        """
        Add entries to the deferred downloading (lazy) catalog.

        :param units: A list of: pulp_rpm.plugins.db.models.ISO.
        :type units: list
        """
        for unit in units:
            unit.set_storage_path(unit.name)
            entry = LazyCatalogEntry()
            entry.path = unit.storage_path
            entry.importer_id = str(self.sync_conduit.importer_object_id)
            entry.unit_id = unit.id
            entry.unit_type_id = unit.type_id
            entry.url = unit.url
            entry.save_revision()

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

        # Discover what files we need to download and what we already have
        filtered_isos = self._filter_missing_isos(manifest)
        local_missing_isos, local_available_isos, remote_missing_isos = filtered_isos

        # Associate units that are already in Pulp
        if local_available_isos:
            search_dicts = [unit.unit_key for unit in local_available_isos]
            self.sync_conduit.associate_existing(models.ISO._content_type_id, search_dicts)

        # Deferred downloading (Lazy) entries.
        self.add_catalog_entries(local_missing_isos)

        self.progress_report.state = self.progress_report.STATE_ISOS_IN_PROGRESS

        # Download files and add units.
        if self.download_deferred:
            for iso in local_missing_isos:
                iso.downloaded = False
                iso.save()
                repo_controller.associate_single_unit(self.sync_conduit.repo, iso)
        else:
            self._download_isos(local_missing_isos)

        # Remove unwanted iso units
        if self._remove_missing_units:
            repo_controller.disassociate_units(self.sync_conduit.repo, remote_missing_isos)

        # Report that we are finished. Note that setting the
        # state to STATE_ISOS_COMPLETE will automatically set the state to STATE_ISOS_FAILED if the
        # progress report has collected any errors. See the progress_report's _set_state() method
        # for the implementation of this logic.
        self.progress_report.state = self.progress_report.STATE_COMPLETE
        report = self.progress_report.build_final_report()
        return report

    def _download_isos(self, manifest):
        """
        Makes the calls to retrieve the ISOs from the manifest, storing them on disk and
        recording them in the Pulp database.

        :param manifest: The manifest containing a list of ISOs we want to download.
        :type  manifest: pulp_rpm.plugins.db.models.ISOManifest
        """
        self.progress_report.total_bytes = 0
        self.progress_report.num_isos = len(manifest)
        # For each ISO in the manifest, we need to determine a relative path where we want
        # it to be stored, and initialize the Unit that will represent it
        for iso in manifest:
            iso.bytes_downloaded = 0
            # Set the total bytes onto the report
            self.progress_report.total_bytes += iso.size
        self.progress_report.update_progress()
        # We need to build a list of DownloadRequests
        download_directory = common_utils.get_working_directory()
        download_requests = []
        for iso in manifest:
            iso_tmp_dir = tempfile.mkdtemp(dir=download_directory)
            iso_name = os.path.basename(iso.url)
            iso_download_path = os.path.join(iso_tmp_dir, iso_name)
            download_requests.append(request.DownloadRequest(iso.url, iso_download_path, iso))
        self.downloader.download(download_requests)

    def _download_manifest(self):
        """
        Download the manifest file, and process it to return an ISOManifest.

        :return: manifest of available ISOs
        :rtype:  pulp_rpm.plugins.db.models.ISOManifest
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
        except ValueError:
            self.progress_report.error_message = _('The PULP_MANIFEST file was not in the ' +
                                                   'expected format.')
            self.progress_report.state = self.progress_report.STATE_MANIFEST_FAILED
            raise ValueError(self.progress_report.error_message)

        return manifest

    def _filter_missing_isos(self, manifest):
        """
        Use the sync_conduit and the manifest to determine which ISOs are at the feed_url
        that are not in our local store, as well as which ISOs are in our local store that are not
        available at the feed_url.

        :param manifest: An ISOManifest describing the ISOs that are available at the
                         feed_url that we are synchronizing with
        :type  manifest: pulp_rpm.plugins.db.models.ISOManifest
        :return:         A 3-tuple. The first element of the tuple is a list of ISOs that we should
                         retrieve from the feed_url. The second element of the tuple is a list of
                         Units that are available locally already, but are not currently associated
                         with the repository. The third element of the tuple is a list of Units that
                         represent the ISOs that we have in our local repo that were not found in
                         the remote repo.
        :rtype:          tuple
        """
        # A list of all the ISOs we have in Pulp
        existing_units = models.ISO.objects()
        existing_units_by_key = dict([(unit.unit_key_str, unit)
                                      for unit in existing_units])
        existing_units.rewind()
        existing_unit_keys = set([unit.unit_key_str
                                  for unit in existing_units])

        # A list of units currently associated with the repository
        existing_repo_units = repo_controller.find_repo_content_units(
            self.sync_conduit.repo, yield_content_unit=True)
        existing_repo_units = list(existing_repo_units)
        existing_repo_units_by_key = dict([(unit.unit_key_str, unit)
                                           for unit in existing_repo_units])
        existing_repo_unit_keys = set([unit.unit_key_str
                                       for unit in existing_repo_units])

        # A list of the ISOs in the remote repository
        available_isos_by_key = dict([(iso.unit_key_str, iso) for iso in manifest])
        available_iso_keys = set([iso.unit_key_str for iso in manifest])

        # Content that is available locally and just needs to be associated with the repository
        local_available_iso_keys = set([iso for iso in available_iso_keys
                                        if iso in existing_unit_keys])
        local_available_iso_keys = local_available_iso_keys - existing_repo_unit_keys
        local_available_units = [existing_units_by_key[k] for k in local_available_iso_keys]

        # Content that is missing locally and must be downloaded
        local_missing_iso_keys = list(available_iso_keys - existing_unit_keys)
        local_missing_isos = [available_isos_by_key[k] for k in local_missing_iso_keys]

        # Content that is missing from the remote repository that is present locally
        remote_missing_unit_keys = list(existing_repo_unit_keys - available_iso_keys)
        remote_missing_units = [existing_repo_units_by_key[k] for k in remote_missing_unit_keys]

        return local_missing_isos, local_available_units, remote_missing_units
