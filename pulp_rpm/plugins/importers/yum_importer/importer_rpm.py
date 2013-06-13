# -*- coding: utf-8 -*-
#
# Copyright © 2012-2013 Red Hat, Inc.
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
import itertools
import os
import Queue
import shutil
import threading
import time

from grinder.BaseFetch import BaseFetch
from grinder.GrinderCallback import ProgressReport
from grinder.RepoFetch import YumRepoGrinder
from yum_importer import distribution, drpm

import pulp_rpm.common.constants as constants
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp_rpm.common.ids import TYPE_ID_DISTRO, TYPE_ID_YUM_REPO_METADATA_FILE
from pulp_rpm.yum_plugin import util, metadata

_LOG = util.getLogger(__name__)

RPM_TYPE_ID="rpm"
SRPM_TYPE_ID="srpm"
RPM_UNIT_KEY = ("name", "epoch", "version", "release", "arch", "checksum", "checksumtype")


PROGRESS_REPORT_FIELDS = ["state", "items_total", "items_left", "size_total", "size_left",
    "num_error", "num_success", "details", "error_details"]

def get_existing_units(sync_conduit, criteria=None):
   """
   @param sync_conduit
   @type sync_conduit pulp.server.content.conduits.repo_sync.RepoSyncConduit

   @return a dictionary of existing units, key is the rpm lookup_key and the value is the unit
   @rtype {():pulp.server.content.plugins.model.Unit}
   """
   existing_units = {}
   for u in sync_conduit.get_units(criteria):
       key = form_lookup_key(u.unit_key)
       existing_units[key] = u
   return existing_units

def get_available_rpms(rpm_items):
    """
    @param rpm_items list of dictionaries containing info on each rpm, see grinder.YumInfo.__getRPMs() for more info
    @type rpm_items [{}]

    @return a dictionary, key is the rpm lookup_key and the value is a dictionary with rpm info
    @rtype {():{}}
    """
    available_rpms = {}
    for rpm in rpm_items:
        key = form_lookup_key(rpm)
        available_rpms[key] = rpm
    return available_rpms

def get_orphaned_units(available_rpms, existing_units):
    """
    @param available_rpms a dict of rpms
    @type available_rpms {}

    @param existing_units dict of units
    @type existing_units {key:pulp.server.content.plugins.model.Unit}

    @return a dictionary of orphaned units, key is the rpm lookup_key and the value is the unit
    @rtype {key:pulp.server.content.plugins.model.Unit}
    """
    orphaned_units = {}
    for key in existing_units:
        if key not in available_rpms:
            orphaned_units[key] = existing_units[key]
    return orphaned_units

def get_new_rpms_and_units(available_rpms, existing_units, sync_conduit):
    """
    Determines what rpms are new and will initialize new units to match these rpms

    @param available_rpms a dict of available rpms
    @type available_rpms {}

    @param existing_units dict of existing Units
    @type existing_units {pulp.server.content.plugins.model.Unit}

    @param sync_conduit
    @type sync_conduit pulp.server.content.conduits.repo_sync.RepoSyncConduit

    @return a tuple of 2 dictionaries.  First dict is of missing rpms, second dict is of missing units
    @rtype ({}, {})
    """
    new_rpms = {}
    new_units = {}
    for key in available_rpms:
        if key not in existing_units:
            rpm = available_rpms[key]
            new_rpms[key] = rpm
            unit_key = form_rpm_unit_key(rpm)
            metadata = form_rpm_metadata(rpm)
            pkgpath = os.path.join(rpm["pkgpath"], metadata["filename"])
            if rpm['arch'] == 'src':
                # initialize unit as a src rpm
                new_units[key] = sync_conduit.init_unit(SRPM_TYPE_ID, unit_key, metadata, pkgpath)
            else:
                new_units[key] = sync_conduit.init_unit(RPM_TYPE_ID, unit_key, metadata, pkgpath)
            # We need to determine where the unit should be stored and update
            # rpm["pkgpath"] so Grinder will store the rpm to the correct location
            rpm["pkgpath"] = os.path.dirname(new_units[key].storage_path)
    return new_rpms, new_units

def get_missing_rpms_and_units(available_rpms, existing_units, verify_options={}):
    """
    @param available_rpms dict of available rpms
    @type available_rpms {}

    @param existing_units dict of existing Units
    @type existing_units {key:pulp.server.content.plugins.model.Unit}

    @return a tuple of 2 dictionaries.  First dict is of missing rpms, second dict is of missing units
    @rtype ({}, {})
    """
    missing_rpms = {}
    missing_units = {}
    for key in available_rpms:
        if key in existing_units:
            rpm_path = existing_units[key].storage_path
            if not util.verify_exists(rpm_path, existing_units[key].unit_key.get('checksum'),
                existing_units[key].unit_key.get('checksumtype'), verify_options):
                _LOG.debug("Missing an existing unit: %s.  Will add to resync." % (rpm_path))
                missing_rpms[key] = available_rpms[key]
                missing_units[key] = existing_units[key]
                # Adjust storage path to match intended location
                # Grinder will use this 'pkgpath' to write the file
                missing_rpms[key]["pkgpath"] = os.path.dirname(missing_units[key].storage_path)
    return missing_rpms, missing_units

def form_rpm_unit_key(rpm):
    unit_key = {}
    for key in RPM_UNIT_KEY:
        unit_key[key] = rpm[key]
    return unit_key

def form_rpm_metadata(rpm):
    metadata = {}
    for key in ("filename", "relativepath"):
        metadata[key] = rpm[key]
    return metadata

def form_lookup_key(rpm):
    rpm_key = (rpm["name"], rpm["epoch"], rpm["version"], rpm['release'], rpm["arch"], rpm["checksumtype"], rpm["checksum"])
    return rpm_key

def form_report(report):
    """
    @param report grinder synchronization report
    @type report grinder.ParallelFetch.SyncReport

    @return dict
    @rtype dict
    """
    ret_val = {}
    ret_val["successes"] = report.successes
    ret_val["downloads"] = report.downloads
    ret_val["errors"] = report.errors
    ret_val["details"] = report.last_progress.details
    ret_val["error_details"] = report.last_progress.error_details
    ret_val["items_total"] = report.last_progress.items_total
    ret_val["items_left"] = report.last_progress.items_left
    ret_val["size_total"] = report.last_progress.size_total
    ret_val["size_left"] = report.last_progress.size_left
    return ret_val

def force_ascii(value):
    retval = value
    if isinstance(value, unicode):
        retval = value.encode('ascii', 'ignore')
    return retval


def get_yumRepoGrinder(repo_id, repo_working_dir, config):
    """
    @param repo_id repo id
    @type repo_id str

    @param tmp_path temporary path for sync
    @type tmp_path str

    @param config plugin config parameters
    @param config pulp.server.content.plugins.config.PluginCallConfiguration

    @return an instantiated YumRepoGrinder instance
    @rtype grinder.RepoFetch.YumRepoGrinder
    """
    repo_label = repo_id
    repo_url = config.get("feed_url")
    num_threads = config.get("num_threads") or 4
    proxy_url = force_ascii(config.get("proxy_url"))
    proxy_port = force_ascii(config.get("proxy_port"))
    proxy_user = force_ascii(config.get("proxy_user"))
    proxy_pass = force_ascii(config.get("proxy_pass"))
    sslverify = config.get_boolean("ssl_verify")
    # Default to verifying SSL
    if sslverify is None:
        sslverify = True
    # Note ssl_ca_cert, ssl_client_cert, and ssl_client_key are all written in the main importer
    # int the validate_config method
    cacert = None
    if config.get("ssl_ca_cert"):
        cacert = os.path.join(repo_working_dir, "ssl_ca_cert").encode('utf-8')
    clicert = None
    if config.get("ssl_client_cert"):
        clicert = os.path.join(repo_working_dir, "ssl_client_cert").encode('utf-8')
    clikey = None
    if config.get("ssl_client_key"):
        clikey = os.path.join(repo_working_dir, "ssl_client_key").encode('utf-8')
    max_speed = config.get("max_speed")
    newest = config.get("newest") or False
    remove_old = config.get("remove_old") or False
    purge_orphaned = config.get("purge_orphaned") or True
    num_old_packages = config.get("num_old_packages") or 0
    skip = config.get("skip") or []
    yumRepoGrinder = YumRepoGrinder(repo_label=repo_label, repo_url=repo_url, parallel=num_threads,\
        mirrors=None, newest=newest, cacert=cacert, clicert=clicert, clikey=clikey,\
        proxy_url=proxy_url, proxy_port=proxy_port, proxy_user=proxy_user,\
        proxy_pass=proxy_pass, sslverify=sslverify, packages_location="./",\
        remove_old=remove_old, numOldPackages=num_old_packages, skip=skip, max_speed=max_speed,\
        purge_orphaned=purge_orphaned, distro_location=constants.DISTRIBUTION_STORAGE_PATH, tmp_path=repo_working_dir)
    return yumRepoGrinder

def _search_for_error(rpm_dict):
    errors = {}
    for key in rpm_dict:
        if rpm_dict[key].has_key("error"):
            _LOG.debug("Saw an error with: %s" % (rpm_dict[key]))
            errors[key] = rpm_dict[key]
    return errors

def search_for_errors(new_rpms, missing_rpms):
    errors = {}
    errors.update(_search_for_error(new_rpms))
    errors.update(_search_for_error(missing_rpms))
    return errors

def remove_unit(sync_conduit, unit):
    """
    @param sync_conduit
    @type sync_conduit L{pulp.server.content.conduits.repo_sync.RepoSyncConduit}

    @param unit
    @type unit L{pulp.server.content.plugins.model.Unit}

    Goals:
     UnAssociate the unit from the database and let pulp clean the filesystem
    """
    _LOG.info("Unassociating unit <%s>" % (unit))
    sync_conduit.remove_unit(unit)

def set_repo_checksum_type(repo, sync_conduit, config):
    """
      At this point we have downloaded the source metadata from a remote or local feed
      lets lookup the checksum type for primary xml in repomd.xml and use that for createrepo

      @param repo: metadata describing the repository
      @type  repo: L{pulp.server.content.plugins.data.Repository}

      @param sync_conduit
      @type sync_conduit pulp.server.content.conduits.repo_sync.RepoSyncConduit

      @param config: plugin configuration
      @type  config: L{pulp.server.content.plugins.config.PluginCallConfiguration}
    """
    _LOG.debug('Determining checksum type for repo %s' % repo.id)
    checksum_type = config.get('checksum_type')
    if checksum_type:
        if not util.is_valid_checksum_type(checksum_type):
            _LOG.error("Invalid checksum type [%s]" % checksum_type)
            raise
    else:
        repo_metadata = os.path.join(repo.working_dir, repo.id, "repodata/repomd.xml")
        if os.path.exists(repo_metadata):
            checksum_type = util.get_repomd_filetype_dump(repo_metadata)['primary']['checksum'][0]
            _LOG.debug("got checksum type from repo %s " % checksum_type)
        else:
            # default to sha256 if nothing is found
            checksum_type = "sha256"
            _LOG.debug("got checksum type default %s " % checksum_type)

    # set repo checksum type on the scratchpad for distributor to lookup
    sync_conduit.set_repo_scratchpad(dict(checksum_type=checksum_type))
    _LOG.info("checksum type info [%s] set to repo scratchpad" % sync_conduit.get_repo_scratchpad())


def preserve_custom_metadata_on_scratchpad(repo, sync_conduit, config):
    """
    Preserve custom metadata from repomd.xml on scratchpad for distributor to lookup and
    publish. This includes prestodelta, productid or any other filetype that isn't the
    standard.
      @param repo: metadata describing the repository
      @type  repo: L{pulp.server.content.plugins.data.Repository}

      @param sync_conduit
      @type sync_conduit pulp.server.content.conduits.repo_sync.RepoSyncConduit

      @param config: plugin configuration
      @type  config: L{pulp.server.content.plugins.config.PluginCallConfiguration}
    """
    _LOG.debug('Determining custome filetypes to preserve for repo %s' % repo.id)
    # store the importer working dir on scratchpad to lookup downloaded data
    importer_repodata_dir = os.path.join(repo.working_dir, repo.id, "repodata")
    repomd_xml_path = os.path.join(importer_repodata_dir, "repomd.xml")
    if not os.path.exists(repomd_xml_path):
        return
    ftypes = util.get_repomd_filetypes(repomd_xml_path)
    base_ftypes = ['primary', 'primary_db', 'filelists_db', 'filelists', 'other', 'other_db',
                   'group', 'group_gz', 'updateinfo', 'updateinfo_db']
    existing_scratch_pad = sync_conduit.get_repo_scratchpad() or {}
    skip_metadata_types = metadata.convert_content_to_metadata_type(config.get("skip") or [])
    existing_scratch_pad.update({"repodata" : {}})
    for ftype in ftypes:
        if ftype in base_ftypes:
            # no need to process these again
            continue
        if ftype in skip_metadata_types and not skip_metadata_types[ftype]:
            _LOG.info("mdtype %s part of skip metadata; skipping" % ftype)
            continue
        filetype_path = os.path.join(importer_repodata_dir, os.path.basename(util.get_repomd_filetype_path(repomd_xml_path, ftype)))
        if filetype_path.endswith('.gz'):
            # if file is gzipped, decompress
            data = gzip.open(filetype_path).read().decode("utf-8", "replace")
        else:
            data = open(filetype_path).read().decode("utf-8", "replace")
        existing_scratch_pad["repodata"].update({ftype : data})
    sync_conduit.set_repo_scratchpad(existing_scratch_pad)


def associate_custom_metadata_files(repo, sync_conduit, config):
    """
    :param repo: metadata describing the repository
    :type repo: pulp.server.content.plugins.data.Repository

    :param sync_conduit: pulp sync api object
    :type sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit

    :param config: plugin configuration
    :type config: pulp.plugins.config.PluginCallConfiguration
    """
    _LOG.debug('Downloading custom metadata files for repo %s' % repo.id)

    importer_repodata_dir = os.path.join(repo.working_dir, repo.id, 'repodata')
    repomd_file_path = os.path.join(importer_repodata_dir, 'repomd.xml')

    if not os.path.exists(repomd_file_path):
        return

    repomd_ftype_dict = util.get_repomd_filetype_dump(repomd_file_path)

    if not repomd_ftype_dict:
        # no ftypes defined or found
        return

    base_ftype_list = ('primary', 'primary_db', 'filelists_db', 'filelists',
                       'other', 'other_db', 'group', 'group_gz', 'updateinfo',
                       'updateinfo_db')

    skip_ftype_list = metadata.convert_content_to_metadata_type(config.get('skip', []))

    scratch_pad = sync_conduit.get_repo_scratchpad() or {}
    repo_checksum_type = scratch_pad.get('checksum_type', 'sha256')

    for ftype, ftype_data in repomd_ftype_dict.items():

        if ftype in base_ftype_list or ftype in skip_ftype_list:
            # already processed or configured to be skip
            continue

        ftype_file_name = os.path.basename(util.get_repomd_filetype_path(repomd_file_path, ftype))
        ftype_file_path = os.path.join(importer_repodata_dir, ftype_file_name)

        unit_key = {'repo_id': repo.id, 'data_type': ftype}
        unit_metadata = {'checksum_type': repo_checksum_type,
                         'checksum': ftype_data['checksum']}
        relative_path = '%s/%s' % (repo.id, ftype_file_name)

        unit = sync_conduit.init_unit(TYPE_ID_YUM_REPO_METADATA_FILE,
                                      unit_key,
                                      unit_metadata,
                                      relative_path)

        shutil.copyfile(ftype_file_path, unit.storage_path)

        sync_conduit.save_unit(unit)


class SaveUnitThread(threading.Thread):
    """
    Will handle looking up yum repo metadata on RPMs and save the unit to the sync_conduit.
    Does the work in parallel with downloading to increase performance.
    Saves units of: rpm, srpm, drpm
    Note:
        distribution units will pass through this from the Grinder callbacks yet will not be saved.
        a separate method in ImporterRPM will process distribution saves.
    """
    def __init__(self, sync_conduit):
        threading.Thread.__init__(self)
        self.sync_conduit = sync_conduit
        self._stop = threading.Event()
        self.queue_cond = threading.Condition()
        self.download_q = Queue.Queue()
        self.yum_pkg_details = None
        self.error_units = []
        self.saved_unit_keys = []
        self.unit_lookup = {}
        self.running = False
        self.repo_label = ""

    def init(self, repo_dir, repo_label, unit_lookup):
        self.repo_dir = repo_dir
        self.repo_label = repo_label
        self.unit_lookup = {}
        for key, u in unit_lookup.items():
            # Build lookup table based on 'relativepath'
            #  store the 'key' and 'unit' we will require 'key' later to note errors
            if u.metadata.has_key("relativepath"):
                entry = {"key": key, "unit": u}
                self.unit_lookup[u.metadata["relativepath"]] = entry
            elif u.type_id not in (TYPE_ID_DISTRO):
                _LOG.warning("Unable to find 'relativepath' for %s" % (u))

    def __init_yum_package_details(self):
        # This _must_ be init'd in the same thread that will perform the lookups.
        self.yum_pkg_details = metadata.YumPackageDetails(self.repo_dir, self.repo_label)
        if not self.yum_pkg_details.init():
            _LOG.error("<%s> Unable to lookup yum package metadata attributes, failed to initialize YumPackageDetails" % (self.repo_label))
            self.yum_pkg_details.close()
            self.yum_pkg_details = None

    def finish(self):
        counter = 0
        # We will poll a boolean to see when the run method has finished.
        # Requirements/Assumptions:
        #  1) finish() is only called _after_ the producer has finished producing events.
        #       for grinder this means finish() is called after grinder has returned from processing all items.
        #       grinder will only return after all items have been downloaded and all progress updates have been sent
        #       there will be no more items being produced and sent to the Queue.
        #  2) The consumer thread, run() may have finished processing all items on Queue prior to us being called
        #       the consumer thread would be waiting on the Condition Variable at this point and will require a 'notify()'
        #       to wake up.
        #  3) The consumer thread will always process all items on the Queue before waiting on the Condition Variable.
        #       after processing all items, when Queue is empty it will then wait on the Condition Variable
        #  4) The consumer & producer will always aqcuire the lock on the Condition Variable before using the Queue
        #  5) If the consumer is woken up and the Queue is empty we assume no more items will be sent and we exit.
        #
        while self.running:
            self.queue_cond.acquire()
            try:
                self.queue_cond.notify()
            finally:
                self.queue_cond.release()
            if counter % 150 == 0:
                _LOG.info("<%s>Waiting for SaveThread to finish: roughly %s items on queue" % (self.repo_label, self.download_q.qsize()))
            time.sleep(.01)
            counter += 1
        _LOG.info("<%s> SaveThread has finished" % (self.repo_label))

    def get_errors(self):
        return self.error_units

    def get_saved(self):
        return self.saved_unit_keys

    def stop(self):
        self._stop.set()

    def run(self):
        self.running = True
        try:
            self.__run()
        finally:
            self.running = False
            _LOG.info("<%s> SaveThread: Stopped" % (self.repo_label))

    def __run(self):
        _LOG.info("<%s> SaveThread starting" % (self.repo_label))
        # Note:
        #  All of the interactions with self.yum_package_details must be from the same thread.
        #  This is a sqlite requirement.  The below error is related:
        #   "SQLite objects created in a thread can only be used in that same thread."
        #
        self.__init_yum_package_details()
        while not self._stop.isSet():
            try:
                item = self.get_item()
            except Queue.Empty:
                # Note this will only happen if we intend to stop this thread
                # and 'finish()' signals the condition variable
                _LOG.info("<%s> SaveThread: Queue empty will exit" % (self.repo_label))
                break
            self.process_item(item)
        if self.yum_pkg_details:
            self.yum_pkg_details.close()
            del self.yum_pkg_details

    def process_item(self, item):
        """
        @param item dictionary as defined by the 'put_item' method
        @type {}
        """
        a = time.time()
        relativepath = item["relativepath"]
        item_type = item["type"]
        entry = self.lookup_item(relativepath)
        if not entry:
            if item_type not in [BaseFetch.TREE_FILE]:
                _LOG.info("<%s> SaveThread didn't find an entry for '%s' in the lookup table for new units." % (self.repo_label, relativepath))
                _LOG.info("Will assume this item was a 'missing' item being re-fetched, therefore has already been saved in mongo.")
            return
        key = entry["key"]
        unit = entry["unit"]
        if not item["success"]:
            _LOG.warn("<%s> Error noted downloading: %s with relativepath: %s" % (self.repo_label, key, relativepath))
            self.error_units.append(unit)
            return # don't save this unit, continue processing
        b = time.time()
        if item_type in [BaseFetch.RPM]: #Covers rpm & srpm
            unit = self.expand_metadata(relativepath, unit)
        c = time.time()
        if self.save_unit(unit):
            self.saved_unit_keys.append(key)
        else:
            self.error_units.append(unit)
        d = time.time()
        _LOG.debug("<%s> SaveThread<%s on queue>: %s(s) in process_item, %s(s) in expand_metadata, %s(s) seconds in save_unit, saved(%s)" \
            % (self.repo_label, self.download_q.qsize(), d-a, c-b, d-c, unit.unit_key))

    def put_item(self, item):
        """
        @param item consists of keys: ["name", "type", "relativepath", "success"]
                name = item's filename
                type = rpm, drpm, distribution, etc
                relativepath =
                success = true on successful download, false on error
        @type item {}
        """
        self.queue_cond.acquire()
        try:
            self.download_q.put_nowait(item)
            self.queue_cond.notify()
        finally:
            self.queue_cond.release()

    def get_item(self):
        item = None
        self.queue_cond.acquire()
        try:
            if self.download_q.empty():
                self.queue_cond.wait()
            item = self.download_q.get_nowait()
        finally:
            self.queue_cond.release()
        return item

    def lookup_item(self, relativepath):
        """
        Not all items we are notified about will be saved.
        Example:    YumImporter does not re-save a "missing" item.
                    A missing item, would be a RPM that was downloaded/saved prior
                    yet for some reason it now no longer exists.
                    Grinder will re-download the item, yet YumImporter will not re-save.
                    This leave us open to a potential problem.
                      What if an item does not change, but the metadata for it does change?
                      YumImporter would not account for this sort of difference.
        @param relativepath used as a key to find the corresponding unit instance
        @type str
        @return unit
        @rtype L{pulp.server.content.plugins.model.Unit}
        """
        if self.unit_lookup.has_key(relativepath):
            return self.unit_lookup[relativepath]
        return None

    def expand_metadata(self, relativepath, u):
        """
        @param relativepath of unit, used as lookup to match yum package metadata
        @type relativepath str
        @return an expanded unit that has yum package metadata filled out, if unit was a RPM
        @rtype L{pulp.server.content.plugins.model.Unit}
        """
        if u.type_id in [RPM_TYPE_ID, SRPM_TYPE_ID] and self.yum_pkg_details:
            u.metadata.update(self.yum_pkg_details.get_details(relativepath))
        return u

    def save_unit(self, u):
        """
        @param u a unit to be saved
        @type u L{pulp.server.content.plugins.model.Unit}
        """
        try:
            self.sync_conduit.save_unit(u)
            if u.type_id in [RPM_TYPE_ID, SRPM_TYPE_ID] and self.yum_pkg_details:
                # Remove "repodata" and "changelog" from each unit to save on memory
                if u.metadata.has_key("repodata"):
                    del u.metadata["repodata"]
                if u.metadata.has_key("changelog"):
                    del u.metadata["changelog"]
            return True
        except Exception, e:
            _LOG.exception("<%s> Unable to save unit: %s" % (self.repo_label, u))
            return False


class ImporterRPM(object):
    def __init__(self):
        self.canceled = False
        self.yumRepoGrinder = None
        self.save_thread = None

    def sync(self, repo, sync_conduit, config, importer_progress_callback=None):
        """
          Invokes RPM sync sequence

          @param repo: metadata describing the repository
          @type  repo: L{pulp.server.content.plugins.data.Repository}

          @param sync_conduit
          @type sync_conduit pulp.server.content.conduits.repo_sync.RepoSyncConduit

          @param config: plugin configuration
          @type  config: L{pulp.server.content.plugins.config.PluginCallConfiguration}

          @param importer_progress_callback callback to report progress info to sync_conduit
          @type importer_progress_callback function

          @return a tuple of state, dict of sync summary and dict of sync details
          @rtype (bool, {}, {})
        """
        self.save_thread = SaveUnitThread(sync_conduit) # save_thread needs to be accessible inside progress_callback()

        def set_progress(type_id, status):
            if importer_progress_callback:
                importer_progress_callback(type_id, status)

        def cleanup_error_details(error_details):
            for error in error_details:
                if error.has_key("exception"):
                    error["exception"] = str(error["exception"])
            return error_details

        def progress_callback(report):
            """
            @param report progress report from Grinder
            @type report: grinder.GrinderCallback.ProgressReport
            """
            status = {}
            #_LOG.info("progress_callback: <%s>" % (report))

            if ProgressReport.DownloadItems in report.step:
                status = {}
                if report.status == "FINISHED":
                    if self.canceled:
                        status["state"] = "CANCELED"
                    else:
                        status["state"] = "FINISHED"
                else:
                    status["state"] = "IN_PROGRESS"
                status["num_success"] = report.num_success
                status["num_error"] = report.num_error
                status["size_left"] = report.size_left
                status["size_total"] = report.size_total
                status["items_left"] = report.items_left
                status["items_total"] = report.items_total
                status["error_details"] = cleanup_error_details(report.error_details)
                status["details"] = {}
                if report.details:
                    for key in report.details.keys():
                        status["details"][key] = {}
                        status["details"][key]["num_success"] = report.details[key]["num_success"]
                        status["details"][key]["num_error"] = report.details[key]["num_error"]
                        status["details"][key]["size_left"] = report.details[key]["size_left"]
                        status["details"][key]["size_total"] = report.details[key]["total_size_bytes"]
                        status["details"][key]["items_left"] = report.details[key]["items_left"]
                        status["details"][key]["items_total"] = report.details[key]["total_count"]
                expected_details = (BaseFetch.RPM, BaseFetch.DELTA_RPM, BaseFetch.TREE_FILE, BaseFetch.FILE)
                for key in expected_details:
                    if key not in status["details"].keys():
                        status["details"][key] = {}
                        status["details"][key]["num_success"] = 0
                        status["details"][key]["num_error"] = 0
                        status["details"][key]["size_left"] = 0
                        status["details"][key]["size_total"] = 0
                        status["details"][key]["items_left"] = 0
                        status["details"][key]["items_total"] = 0
                # When grinder completes downloading an item it will set item_complete to True
                if hasattr(report, "item_complete") and report.item_complete:
                    # An item has completed downloading, this would not show up for an incremental progress download
                    saved_item = {
                        "name": report.item_name,
                        "type": report.item_type,
                        "relativepath": report.item_relativepath,
                        "success": report.item_download_success}
                    self.save_thread.put_item(saved_item)
                set_progress("content", status)

        ####
            # Syncs operate on 2 types of data structures
            # 1) RPM info, each 'rpm' is a single dictionary of key/value pairs created in grinder.YumInfo.__getRPMs()
            # 2) Pulp's Unit model, pulp.server.content.plugins.model.Unit
            #
            # Grinder talks in rpms
            # Pulp talks in Units
        ####
        start = time.time()
        feed_url = config.get("feed_url")
        num_retries = config.get("num_retries")
        retry_delay = config.get("retry_delay")
        skip_content_types = config.get("skip") or []
        verify_checksum = config.get("verify_checksum") or False
        verify_size = config.get("verify_size") or False
        verify_options = {"checksum":verify_checksum, "size":verify_size}
        _LOG.info("Begin sync of repo <%s> from feed_url <%s>" % (repo.id, feed_url))
        start_metadata = time.time()
        self.yumRepoGrinder = get_yumRepoGrinder(repo.id, repo.working_dir, config)
        set_progress("metadata", {"state": "IN_PROGRESS"})
        try:
            self.yumRepoGrinder.setup(basepath=repo.working_dir, callback=progress_callback,
                num_retries=num_retries, retry_delay=retry_delay)
        except Exception, e:
            set_progress("metadata", {"state": "FAILED"})
            _LOG.error("Failed to fetch metadata on: %s" % (feed_url))
            raise
        set_progress("metadata", {"state": "FINISHED"})
        end_metadata = time.time()
        new_units = {}

        # ----------------- setup items to download and add to grinder ---------------
        # setup rpm items
        rpm_info = self._setup_rpms(repo, sync_conduit, verify_options, skip_content_types)
        new_units.update(rpm_info['new_rpm_units'])
        # Sync the new and missing rpms
        self.yumRepoGrinder.addItems(rpm_info['new_rpms'].values())
        self.yumRepoGrinder.addItems(rpm_info['missing_rpms'].values())

        # setup drpm items
        drpm_info = self._setup_drpms(repo, sync_conduit, verify_options, skip_content_types)
        new_units.update(drpm_info['new_drpm_units'])
        # Sync the new and missing drpms
        self.yumRepoGrinder.addItems(drpm_info['new_drpms'].values())
        self.yumRepoGrinder.addItems(drpm_info['missing_drpms'].values())

        # setup distribution items
        distro_info = self._setup_distros(repo, sync_conduit, verify_options, skip_content_types)
        new_units.update(distro_info['new_distro_units'])
        all_new_distro_files = list(itertools.chain(*distro_info['new_distro_files'].values()))
        # Sync the new and missing distro
        self.yumRepoGrinder.addItems(all_new_distro_files)
        all_missing_distro_files = list(itertools.chain(*distro_info['missing_distro_files'].values()))
        self.yumRepoGrinder.addItems(all_missing_distro_files)

        #----------- start the item download via grinder ---------------
        start_download = time.time()
        # save_thread needs init() to be called after the yum metadata has been downloaded with yumRepoGrinder.setUp()
        #   further it needs to build a look up table of the initialized units with 'new_units'
        #   expecting yum package metadata to be at repo.working_dir/repo.id
        self.save_thread.init(repo.working_dir, repo.id, new_units)
        self.save_thread.start()
        report = self.yumRepoGrinder.download()
        if self.canceled:
            _LOG.info("Sync of %s has been canceled." % repo.id)
            return False, {}, {}
        end_download = time.time()
        _LOG.info("Finished download of %s in %s seconds.  %s" % (repo.id, end_download-start_download, report))
        # determine the checksum type from downloaded metadata
        set_repo_checksum_type(repo, sync_conduit, config)
        # (XXX remove me) preserve the custom metadata on scratchpad to lookup downloaded data
        #preserve_custom_metadata_on_scratchpad(repo, sync_conduit, config)
        # custom metadata files are now associated with the repo as first-class
        # content units
        associate_custom_metadata_files(repo, sync_conduit, config)

        self.save_thread.finish()  # Wait for all packages to be saved
        not_synced = self.save_thread.get_errors()
        saved_units = self.save_thread.get_saved()
        _LOG.info("SaveThread saved %s units, and reported %s as not_synced" % (len(saved_units), len(not_synced)))

        self.process_distributions(sync_conduit, distro_info["new_distro_units"])

        # -------------- removed orphaned items ---------------
        removal_errors = self.process_orphan_items(repo, sync_conduit, skip_content_types, rpm_info, drpm_info, distro_info)

        # -------------- process the download results to a report ---------------
        summary = self.build_summary(skip_content_types, not_synced, removal_errors,
            rpm_info, drpm_info, distro_info,
            all_new_distro_files, all_missing_distro_files)
        end = time.time()
        summary["time_total_sec"] = end - start
        details = {}
        details["size_total"] = report.last_progress.size_total
        details["time_metadata_sec"] = end_metadata - start_metadata
        details["time_download_sec"] = end_download - start_download
        details["not_synced"] = [x.unit_key for x in not_synced]
        details["sync_report"] = form_report(report)

        status = True
        if removal_errors or details["sync_report"]["errors"]:
            status = False
        _LOG.info("STATUS: %s; SUMMARY: %s; DETAILS: %s" % (status, summary, details))
        return status, summary, details

    def process_distributions(self, sync_conduit, new_distro_units):
        # Distributions need to be saved a little different
        #  A DistributionUnit represents a collection.  A collection of distribution files
        #  As we are downloading each file we receive a callback when they succeed...yet we have nothing to update in the database at that point in time.
        #  Our model is at the level of the entire Distribution, not at individual files making up that collection.
        #
        #  This means that the SaveThread will not be updating anything or Distributions.  The individual files will still be transfered by Grinder
        #  and written to the file system...the update of the DB is the missing piece we need to address here.
        #
        errors = {}
        for key, unit in new_distro_units.items():
            valid = True # If all the files are present we assume Distribution is good and we save it.
            for ksfile in unit.metadata["files"]:
                ks_file_path = os.path.join(unit.storage_path, ksfile["relativepath"])
                if not os.path.exists(ks_file_path):
                    _LOG.info("Unable to save Distribution<%s> because one of it's distribution files: '%s' is missing" % (unit, ks_file_path))
                    valid = False
                    break
            if valid:
                sync_conduit.save_unit(unit)
            else:
                errors[key] = unit
        return errors

    def process_orphan_items(self, repo, sync_conduit, skip_content_types, rpm_info, drpm_info, distro_info):
        errors = {}
        not_synced = []
        removal_errors = []
        # RPMS
        if 'rpm' not in skip_content_types:
            for u in rpm_info['orphaned_rpm_units'].values():
                try:
                    remove_unit(sync_conduit, u)
                except Exception, e:
                    unit_info = str(u.unit_key)
                    _LOG.exception("Unable to remove: %s" % (unit_info))
                    removal_errors.append((unit_info, str(e)))
        # DRPMS
        if 'drpm' not in skip_content_types:
            drpm.purge_orphaned_drpm_units(sync_conduit, repo, drpm_info['orphaned_drpm_units'].values())
        # Distributions
        if 'distribution' not in skip_content_types:
            for u in distro_info['orphaned_distro_units'].values():
                try:
                    remove_unit(sync_conduit, u)
                except Exception, e:
                    unit_info = str(u.unit_key)
                    _LOG.exception("Unable to remove: %s" % (unit_info))
                    removal_errors.append((unit_info, str(e)))
        return removal_errors

    def build_summary(self, skip_content_types, not_synced, removal_errors,
            rpm_info, drpm_info, distro_info,
            all_new_distro_files, all_missing_distro_files):
        # We are removing the older approach of using filter to create a new list and then checking the length
        # Instead we will use reduce and compute the length without requiring extra memory for an additional new list
        _LOG.info("not_synced = %s" % (not_synced))
        if not_synced:
            _LOG.warning("%s items were not downloaded" % (len(not_synced)))
        summary = {}
        summary["removal_errors"] = removal_errors

        if 'rpm' not in skip_content_types:
            def check_rpm(accum, u):
                if u.type_id == 'rpm':
                    return accum+1
                return accum
            summary["num_rpms"] = len(rpm_info['available_rpms'])
            summary["num_synced_new_rpms"] =  reduce(check_rpm, rpm_info['new_rpm_units'].values(), 0)
            summary["num_resynced_rpms"] = reduce(check_rpm, rpm_info['missing_rpm_units'].values(), 0)
            summary["num_not_synced_rpms"] = reduce(check_rpm, not_synced, 0)
            summary["num_orphaned_rpms"] = reduce(check_rpm, rpm_info['orphaned_rpm_units'].values(), 0)

            def check_srpm(accum, u):
                if u.type_id == 'srpm':
                    return accum+1
                return accum
            summary["num_synced_new_srpms"] = reduce(check_srpm, rpm_info['new_rpm_units'].values(), 0)
            summary["num_resynced_srpms"] = reduce(check_srpm, rpm_info['missing_rpm_units'].values(), 0)
            summary["num_not_synced_srpms"] = reduce(check_srpm, not_synced, 0)
            summary["num_orphaned_srpms"] = reduce(check_srpm, rpm_info['orphaned_rpm_units'].values(), 0)

        if 'drpm' not in skip_content_types:
            def check_drpm(accum, u):
                if u.type_id == 'drpm':
                    return accum+1
                return accum
            summary["num_synced_new_drpms"] = len(drpm_info['new_drpm_units'])
            summary["num_resynced_drpms"] = len(drpm_info['missing_drpm_units'])
            summary["num_orphaned_drpms"] = len(drpm_info['orphaned_drpm_units'])
            summary["num_not_synced_drpms"] = reduce(check_drpm, not_synced, 0)

        if 'distribution' not in skip_content_types:
            summary["num_synced_new_distributions"] = len(distro_info['new_distro_units'])
            summary["num_synced_new_distributions_files"] = len(all_new_distro_files)
            summary["num_resynced_distributions"] = len(distro_info['missing_distro_units'])
            summary["num_resynced_distribution_files"] = len(all_missing_distro_files)
            summary["num_orphaned_distributions"] = len(distro_info['orphaned_distro_units'])
        return summary

    def _setup_rpms(self, repo, sync_conduit, verify_options, skip_content_types):
        rpm_info = {'available_rpms' : {}, 'existing_rpm_units' : {}, 'orphaned_rpm_units' : {}, 'new_rpms' : {}, 'new_rpm_units' : {},'missing_rpms' : {}, 'missing_rpm_units' : {}}
        if 'rpm' in skip_content_types:
            _LOG.info("skipping rpm item setup")
            return rpm_info
        start_metadata = time.time()
        rpm_items = self.yumRepoGrinder.getRPMItems()
        rpm_info['available_rpms'] = get_available_rpms(rpm_items)
        end_metadata = time.time()
        _LOG.info("%s rpms are available in the source repo %s, calculated in %s seconds" % \
                    (len(rpm_info['available_rpms']), repo.id, (end_metadata-start_metadata)))

        # Determine what exists and what has been orphaned, or exists in Pulp but has been removed from the source repo
        # Limit the data we retrieve from the DB to reduce memory consumption
        valid_fields = []
        valid_fields.extend(RPM_UNIT_KEY)
        valid_fields.append("_storage_path")
        rpm_info['existing_rpm_units'] = {}
        criteria = UnitAssociationCriteria(type_ids=[SRPM_TYPE_ID], unit_fields=valid_fields)
        rpm_info['existing_rpm_units'].update(get_existing_units(sync_conduit, criteria))
        criteria = UnitAssociationCriteria(type_ids=[RPM_TYPE_ID], unit_fields=valid_fields)
        rpm_info['existing_rpm_units'].update(get_existing_units(sync_conduit, criteria))
        rpm_info['orphaned_rpm_units'] = get_orphaned_units(rpm_info['available_rpms'], rpm_info['existing_rpm_units'])

        # Determine new and missing items
        rpm_info['new_rpms'], rpm_info['new_rpm_units'] = get_new_rpms_and_units(rpm_info['available_rpms'], rpm_info['existing_rpm_units'], sync_conduit)
        rpm_info['missing_rpms'], rpm_info['missing_rpm_units'] = get_missing_rpms_and_units(rpm_info['available_rpms'], rpm_info['existing_rpm_units'], verify_options)
        _LOG.info("Repo <%s> %s existing rpm units, %s have been orphaned, %s new rpms, %s missing rpms." % \
                    (repo.id, len(rpm_info['existing_rpm_units']), len(rpm_info['orphaned_rpm_units']), len(rpm_info['new_rpms']), len(rpm_info['missing_rpms'])))

        return rpm_info

    def _setup_drpms(self, repo, sync_conduit, verify_options, skip_content_types):
        # process deltarpms
        drpm_info = {'available_drpms' : {}, 'existing_drpm_units' : {}, 'orphaned_drpm_units' : {}, 'new_drpms' : {}, 'new_drpm_units' : {}, 'missing_drpms' : {}, 'missing_drpm_units' : {}}
        if 'drpm' in skip_content_types:
            _LOG.info("skipping drpm item setup")
            return drpm_info
        start_metadata = time.time()
        drpm_items = self.yumRepoGrinder.getDeltaRPMItems()
        _LOG.info("Delta RPMs to sync %s" % len(drpm_items))
        drpm_info['available_drpms'] =  drpm.get_available_drpms(drpm_items)
        drpm_info['existing_drpm_units'] = drpm.get_existing_drpm_units(sync_conduit)
        drpm_info['orphaned_drpm_units'] = get_orphaned_units(drpm_info['available_drpms'], drpm_info['existing_drpm_units'])
        end_metadata = time.time()
        _LOG.info("%s drpms are available in the source repo %s, calculated in %s seconds" %\
                  (len(drpm_info['available_drpms']), repo.id, (end_metadata-start_metadata)))

        # Determine new and missing items
        drpm_info['new_drpms'], drpm_info['new_drpm_units'] = drpm.get_new_drpms_and_units(drpm_info['available_drpms'], drpm_info['existing_drpm_units'], sync_conduit)
        drpm_info['missing_drpms'], drpm_info['missing_drpm_units'] = get_missing_rpms_and_units(drpm_info['available_drpms'], drpm_info['existing_drpm_units'], verify_options)
        _LOG.info("Repo <%s> %s existing drpm units, %s have been orphaned, %s new drpms, %s missing drpms." %\
                  (repo.id, len(drpm_info['existing_drpm_units']), len(drpm_info['orphaned_drpm_units']), len(drpm_info['new_drpms']), len(drpm_info['missing_drpms'])))

        return drpm_info

    def _setup_distros(self, repo, sync_conduit, verify_options, skip_content_types):
        distro_info = {'available_distros' : {}, 'existing_distro_units' : {}, 'orphaned_distro_units' : {}, 'new_distro_files' : {}, 'new_distro_units' : {}, 'missing_distro_files' : {}, 'missing_distro_units' : []}
        if 'distribution' in skip_content_types:
            _LOG.info("skipping distribution item setup")
            return distro_info
        start_metadata = time.time()
        self.yumRepoGrinder.setupDistroInfo()
        distro_items = self.yumRepoGrinder.getDistroItems()
        distro_info['available_distros'] = distribution.get_available_distributions(distro_items)
        distro_info['existing_distro_units'] = distribution.get_existing_distro_units(sync_conduit)
        distro_info['orphaned_distro_units'] = distribution.get_orphaned_distros(distro_info['available_distros'], distro_info['existing_distro_units'])
        end_metadata = time.time()
        _LOG.info("%s distributions are available in the source repo %s, calculated in %s seconds" %\
                  (len(distro_info['available_distros']), repo.id, (end_metadata-start_metadata)))
        distro_info['new_distro_files'], distro_info['new_distro_units'] = distribution.get_new_distros_and_units(distro_info['available_distros'], distro_info['existing_distro_units'], sync_conduit)
        distro_info['missing_distro_files'], distro_info['missing_distro_units'] = distribution.get_missing_distros_and_units(distro_info['available_distros'], distro_info['existing_distro_units'], verify_options)
        _LOG.info("Repo <%s> %s existing distro units, %s have been orphaned, %s new distro files, %s missing distro." %\
                  (repo.id, len(distro_info['existing_distro_units']), len(distro_info['orphaned_distro_units']), len(distro_info['new_distro_files']), len(distro_info['missing_distro_files'])))
        return distro_info

    def cancel_sync(self):
        _LOG.info("cancel_sync invoked")
        self.canceled = True
        if self.yumRepoGrinder:
            _LOG.info("Telling grinder to stop syncing")
            self.yumRepoGrinder.stop()
        if self.save_thread:
            self.save_thread.finish()

