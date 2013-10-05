# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import copy
import os
import shutil
import traceback
from gettext import gettext as _

from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common.ids import (
    TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO, TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.yum_plugin import util

from . import configuration, metadata

# -- constants -----------------------------------------------------------------

_LOG = util.getLogger(__name__)

# -- publishing steps ----------------------------------------------------------

PUBLISH_RPMS_STEP = 'rpms'
PUBLISH_DELTA_RPMS_STEP = 'drpms'
PUBLISH_ERRATA_STEP = 'errata'
PUBLISH_PACKAGE_GROUPS_STEP = 'package_groups'
PUBLISH_PACKAGE_CATEGORIES_STEP = 'package_categories'
PUBLISH_DISTRIBUTION_STEP = 'distribution'
PUBLISH_METADATA_STEP = 'metadata'
PUBLISH_OVER_HTTP_STEP = 'publish_over_http'
PUBLISH_OVER_HTTPS_STEP = 'publish_over_https'

PUBLISH_STEPS = (PUBLISH_RPMS_STEP, PUBLISH_DELTA_RPMS_STEP, PUBLISH_ERRATA_STEP,
                 PUBLISH_PACKAGE_GROUPS_STEP, PUBLISH_PACKAGE_CATEGORIES_STEP,
                 PUBLISH_DISTRIBUTION_STEP, PUBLISH_METADATA_STEP,
                 PUBLISH_OVER_HTTP_STEP, PUBLISH_OVER_HTTPS_STEP)

# -- publishing step states ----------------------------------------------------

PUBLISH_NOT_STARTED_STATE = 'NOT_STARTED'
PUBLISH_IN_PROGRESS_STATE = 'IN_PROGRESS'
PUBLISH_SKIPPED_STATE = 'SKIPPED'
PUBLISH_FINISHED_STATE = 'FINISHED'
PUBLISH_FAILED_STATE = 'FAILED'
PUBLISH_CANCELED_STATE = 'CANCELED'

PUBLISH_STATES = (PUBLISH_NOT_STARTED_STATE, PUBLISH_IN_PROGRESS_STATE, PUBLISH_SKIPPED_STATE,
                  PUBLISH_FINISHED_STATE, PUBLISH_FAILED_STATE, PUBLISH_CANCELED_STATE)

# -- publishing reporting ------------------------------------------------------

STATE = 'state'
TOTAL = 'total'
PROCESSED = 'processed'
SUCCESSES = 'successes'
FAILURES = 'failures'
ERROR_DETAILS = 'error_details'

PUBLISH_REPORT_KEYWORDS = (STATE, TOTAL, PROCESSED, SUCCESSES, FAILURES, ERROR_DETAILS)

PROGRESS_REPORT = {PUBLISH_RPMS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_DELTA_RPMS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_ERRATA_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_PACKAGE_GROUPS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_PACKAGE_CATEGORIES_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_DISTRIBUTION_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_METADATA_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_OVER_HTTP_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_OVER_HTTPS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE}}

PROGRESS_SUB_REPORT = {STATE: PUBLISH_IN_PROGRESS_STATE,
                       TOTAL: 0,
                       PROCESSED: 0,
                       SUCCESSES: 0,
                       FAILURES: 0,
                       ERROR_DETAILS: []}

# -- final reporting -----------------------------------------------------------

NUMBER_DISTRIBUTION_UNITS_ATTEMPTED = 'num_distribution_units_attempted'
NUMBER_DISTRIBUTION_UNITS_ERROR = 'num_distribution_units_error'
NUMBER_DISTRIBUTION_UNITS_PUBLISHED = 'num_distribution_units_published'
NUMBER_PACKAGE_CATEGORIES_PUBLISHED = 'num_package_categories_published'
NUMBER_PACKAGE_GROUPS_PUBLISHED = 'num_package_groups_published'
NUMBER_PACKAGE_UNITS_ATTEMPTED = 'num_package_units_attempted'
NUMBER_PACKAGE_UNITS_ERRORS = 'num_package_units_error'
NUMBER_PACKAGE_UNITS_PUBLISHED = 'num_package_units_published'
RELATIVE_PATH = 'relative_path'
SKIP_METADATA_UPDATE = 'skip_metadata_update'

SUMMARY_REPORT = {NUMBER_DISTRIBUTION_UNITS_ATTEMPTED: 0,
                  NUMBER_DISTRIBUTION_UNITS_ERROR: 0,
                  NUMBER_DISTRIBUTION_UNITS_PUBLISHED: 0,
                  NUMBER_PACKAGE_CATEGORIES_PUBLISHED: 0,
                  NUMBER_PACKAGE_GROUPS_PUBLISHED: 0,
                  NUMBER_PACKAGE_UNITS_ATTEMPTED: 0,
                  NUMBER_PACKAGE_UNITS_ERRORS: 0,
                  NUMBER_PACKAGE_UNITS_PUBLISHED: 0,
                  RELATIVE_PATH: None,
                  SKIP_METADATA_UPDATE: False}

ERRORS_LIST = 'errors'
METADATA_GENERATION_TIME = 'time_metadata_sec'

DETAILS_REPORT = {ERRORS_LIST: [],
                  METADATA_GENERATION_TIME: 0}

# -- package fields ------------------------------------------------------------

PACKAGE_FIELDS = ['id', 'name', 'version', 'release', 'arch', 'epoch',
                  '_storage_path', 'checksum', 'checksumtype', 'repodata']

# -- publisher class -----------------------------------------------------------

class Publisher(object):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, repo, publish_conduit, config):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :return:
        """

        self.repo = repo
        self.conduit = publish_conduit
        self.config = config

        self.progress_report = copy.deepcopy(PROGRESS_REPORT)
        self.canceled = False

    @property
    def skip_list(self):
        skip = self.config.get('skip', {})
        return [k for k,v in skip.items() if v]

    # -- publish api methods ---------------------------------------------------

    def publish(self):
        """
        Publish the contents of the repository and their metadata via HTTP/HTTPS.

        :return: report describing the publication
        :rtype:  pulp.plugins.model.PublishReport
        """

        if not os.path.exists(self.repo.working_dir):
            os.makedirs(self.repo.working_dir, mode=0770)

        self._publish_rpms()

        self._publish_over_http()
        self._publish_over_https()

        self._clear_directory(self.repo.working_dir)

        return self._build_final_report()

    def cancel(self):
        """
        Cancel an in-progress publication.
        """

        if self.canceled:
            return

        self.canceled = True

        # put the reporting logic here so I don't have to put it everywhere
        for sub_report in self.progress_report.values():

            if sub_report[STATE] is PUBLISH_IN_PROGRESS_STATE:
                sub_report[STATE] = PUBLISH_CANCELED_STATE

            elif sub_report[STATE] is PUBLISH_NOT_STARTED_STATE:
                sub_report[STATE] = PUBLISH_SKIPPED_STATE

    # -- publish helper methods ------------------------------------------------

    def _publish_rpms(self): # and srpms too

        if self.canceled:
            return

        if TYPE_ID_RPM in self.skip_list:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_RPMS_STEP)

        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_RPM, TYPE_ID_SRPM],
                                           unit_fields=PACKAGE_FIELDS)

        # XXX memory concerns here, this should return something akin to a db
        # cursor or a generator, but it probably returns a list
        unit_list = self.conduit.get_units(criteria=criteria)

        total = len(unit_list)
        self.progress_report[PUBLISH_RPMS_STEP][TOTAL] = total

        with metadata.PrimaryXMLFileContext(self.repo.working_dir, total) as primary_xml_file_context:

            for unit in unit_list:

                if self.canceled:
                    return

                self._report_progress(PUBLISH_RPMS_STEP)
                self.progress_report[PUBLISH_RPMS_STEP][PROCESSED] += 1

                try:
                    self._symlink_content(unit, self.repo.working_dir)

                except Exception, e:
                    self._record_failure(PUBLISH_RPMS_STEP, e)
                    continue

                try:
                    primary_xml_file_context.add_unit_metadata(unit)

                except Exception, e:
                    self._record_failure(PUBLISH_RPMS_STEP, e)
                    continue

                # success
                self.progress_report[PUBLISH_RPMS_STEP][SUCCESSES] += 1

        if self.progress_report[PUBLISH_RPMS_STEP][FAILURES]:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_FAILED_STATE)

        else:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_FINISHED_STATE)

    def _publish_drpms(self):

        if self.canceled:
            return

        if TYPE_ID_DRPM in self.skip_list:
            self._report_progress(PUBLISH_DELTA_RPMS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_DELTA_RPMS_STEP)

    def _publish_errata(self):

        if self.canceled:
            return

        if TYPE_ID_ERRATA in self.skip_list:
            self._report_progress(PUBLISH_ERRATA_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_ERRATA_STEP)

    def _publish_package_groups(self):

        if self.canceled:
            return

        if TYPE_ID_PKG_GROUP in self.skip_list:
            self._report_progress(PUBLISH_PACKAGE_GROUPS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_PACKAGE_GROUPS_STEP)

    def _publish_package_categories(self):

        if self.canceled:
            return

        if TYPE_ID_PKG_CATEGORY in self.skip_list:
            self._report_progress(PUBLISH_PACKAGE_CATEGORIES_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_PACKAGE_CATEGORIES_STEP)

    def _publish_distribution(self):

        if self.canceled:
            return

        if TYPE_ID_DISTRO in self.skip_list:
            self._report_progress(PUBLISH_DISTRIBUTION_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_DISTRIBUTION_STEP)

    def _publish_metadata(self):

        if self.canceled:
            return

        if TYPE_ID_YUM_REPO_METADATA_FILE in self.skip_list:
            self._report_progress(PUBLISH_METADATA_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_METADATA_STEP)

    def _publish_over_http(self):

        if self.canceled:
            return

        if not self.config.get('http'):
            self._report_progress(PUBLISH_OVER_HTTP_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_OVER_HTTP_STEP)
        self._report_progress(PUBLISH_OVER_HTTP_STEP, total=1)

        root_http_publish_dir = configuration.get_http_publish_dir(self.config)
        repo_relative_dir = configuration.get_repo_relative_path(self.repo, self.config)
        repo_http_publish_dir = os.path.join(root_http_publish_dir, repo_relative_dir)

        parent_dir = os.path.dirname(repo_http_publish_dir)

        try:
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, mode=0770)

            shutil.copytree(self.repo.working_dir, repo_http_publish_dir, symlinks=True)

        except Exception, e:
            self._record_failure(PUBLISH_OVER_HTTP_STEP, e)

        else:
            self.progress_report[PUBLISH_OVER_HTTP_STEP][SUCCESSES] = 1

        self.progress_report[PUBLISH_OVER_HTTP_STEP][PROCESSED] = 1

        if self.progress_report[PUBLISH_OVER_HTTP_STEP][SUCCESSES]:
            self._report_progress(PUBLISH_OVER_HTTP_STEP, state=PUBLISH_FINISHED_STATE)

        else:
            self._report_progress(PUBLISH_OVER_HTTP_STEP, state=PUBLISH_FAILED_STATE)

    def _publish_over_https(self):

        if self.canceled:
            return

        if not self.config.get('https'):
            self._report_progress(PUBLISH_OVER_HTTPS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_OVER_HTTPS_STEP)
        self._report_progress(PUBLISH_OVER_HTTPS_STEP, total=1)

        root_https_publish_dir = configuration.get_https_publish_dir(self.config)
        repo_relative_path = configuration.get_repo_relative_path(self.repo, self.config)
        repo_https_publish_dir = os.path.join(root_https_publish_dir, repo_relative_path)

        parent_dir = os.path.dirname(repo_https_publish_dir)

        try:
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, mode=0770)

            shutil.copytree(self.repo.working_dir, repo_https_publish_dir, symlinks=True)

        except Exception, e:
            self._record_failure(PUBLISH_OVER_HTTPS_STEP, e)

        else:
            self.progress_report[PUBLISH_OVER_HTTPS_STEP][SUCCESSES] = 1

        self.progress_report[PUBLISH_OVER_HTTPS_STEP][PROCESSED] = 1

        if self.progress_report[PUBLISH_OVER_HTTPS_STEP][SUCCESSES]:
            self._report_progress(PUBLISH_OVER_HTTPS_STEP, state=PUBLISH_FINISHED_STATE)

        else:
            self._report_progress(PUBLISH_OVER_HTTPS_STEP, state=PUBLISH_FAILED_STATE)

        # XXX I believe the process_repo_auth_cert_bundle needs to go around here somewhere

    # -- progress methods ------------------------------------------------------

    def _init_step_progress_report(self, step):
        """
        Initialize a progress sub-report for the given step.

        :param step: step to initialize a progress sub-report for
        :type  step: str
        """
        assert step in PUBLISH_STEPS

        self.progress_report[step] = copy.deepcopy(PROGRESS_SUB_REPORT)

    def _report_progress(self, step, **report_details):
        """
        Report the current progress back to the conduit, make any updates to the
        current step as necessary.

        :param step: current step of publication process
        :type  step: str
        :param report_details: keyword argument updates to the current step's
                               progress sub-report (if any)
        """
        assert step in PUBLISH_STEPS
        assert set(report_details).issubset(set(PUBLISH_REPORT_KEYWORDS))

        self.progress_report[step].update(report_details)
        self.conduit.set_progress(self.progress_report)

    def _record_failure(self, step, e=None, tb=None):
        """
        Record a failure in a step's progress sub-report.

        :param step: current step that encountered a failure
        :type  step: str
        :param e: exception instance (if any)
        :type  e: Exception or None
        :param tb: traceback instance (if any)
        :type  tb: Traceback or None
        """
        assert step in PUBLISH_STEPS

        self.progress_report[step][FAILURES] += 1

        error_details = []

        if tb is not None:
            error_details.extend(traceback.format_tb(tb))

        if e is not None:
            error_details.append(e.message)

        if error_details:
            self.progress_report[step][ERROR_DETAILS].append('\n'.join(error_details))

    def _build_final_report(self):
        """
        :return: report describing the publish run
        :rtype:  pulp.plugins.model.PublishReport
        """
        summary = copy.deepcopy(SUMMARY_REPORT)
        details = copy.deepcopy(DETAILS_REPORT)

        summary[RELATIVE_PATH] = configuration.get_repo_relative_path(self.repo, self.config)

        if self.progress_report[PUBLISH_METADATA_STEP][STATE] is PUBLISH_SKIPPED_STATE:
            summary[SKIP_METADATA_UPDATE] = True

        for step in PUBLISH_STEPS:

            # using .get() because the sub-sections won't be there if the step was skipped
            total = self.progress_report[step].get(TOTAL, 0)
            failures = self.progress_report[step].get(FAILURES, 0)
            successes = self.progress_report[step].get(SUCCESSES, 0)

            # XXX include errata?
            if step in (PUBLISH_RPMS_STEP, PUBLISH_DELTA_RPMS_STEP):
                summary[NUMBER_PACKAGE_UNITS_ATTEMPTED] += total
                summary[NUMBER_PACKAGE_UNITS_ERRORS] += failures
                summary[NUMBER_PACKAGE_UNITS_PUBLISHED] += successes

            elif step is PUBLISH_DISTRIBUTION_STEP:
                summary[NUMBER_DISTRIBUTION_UNITS_ATTEMPTED] = total
                summary[NUMBER_DISTRIBUTION_UNITS_ERROR] = failures
                summary[NUMBER_DISTRIBUTION_UNITS_PUBLISHED] = successes

            # XXX expand this to include attempted and error?
            elif step is PUBLISH_PACKAGE_CATEGORIES_STEP:
                summary[NUMBER_PACKAGE_CATEGORIES_PUBLISHED] = successes

            # XXX expand this to include attempted and error?
            elif step is PUBLISH_PACKAGE_GROUPS_STEP:
                summary[NUMBER_PACKAGE_GROUPS_PUBLISHED] = successes

            details[ERRORS_LIST].extend(self.progress_report[step].get(ERROR_DETAILS, []))

        # XXX not sure this is the best criteria, maybe 1 or more failure states?
        if details[ERRORS_LIST]:
            return self.conduit.build_failure_report(summary, details)

        return self.conduit.build_success_report(summary, details)

    # -- linking methods -------------------------------------------------------

    def _symlink_content(self, unit, working_sub_dir):
        """
        Create a symlink to a unit's storage path in the given working subdirectory.

        :param unit: unit to create symlink to
        :type  unit: pulp.plugins.model.Unit
        :param working_sub_dir: working subdirectory to create symlink in
        :type  working_sub_dir: str
        """

        source_path = unit.storage_path
        relative_path = util.get_relpath_from_unit(unit)
        destination_path = os.path.join(working_sub_dir, relative_path)

        self._create_symlink(source_path, destination_path)

    @staticmethod
    def _create_symlink(source_path, link_path):
        """
        Create a symlink from the link path to the source path.

        :param source_path: path of the source to link to
        :type  source_path: str
        :param link_path: path of the link
        :type  link_path: str
        """

        if not os.path.exists(source_path):
            msg = _('Cannot create a symlink to a non-existent source [%(s)s]')
            raise RuntimeError(msg % {'s': source_path})

        if link_path.endswith('/'):
            link_path = link_path[:-1]

        link_parent_dir = os.path.dirname(link_path)

        if not os.path.exists(link_parent_dir):
            os.makedirs(link_parent_dir, mode=0770)

        elif not os.access(link_parent_dir, os.R_OK | os.W_OK | os.X_OK):
            msg = _('Insufficient permissions to create symlink in directory [%(d)s]')
            raise RuntimeError(msg % {'d': link_parent_dir})

        elif os.path.lexists(link_path):

            if os.path.islink(link_path):

                link_target = os.readlink(link_path)

                if link_target == source_path:
                    return

                msg = _('Removing old link [%(l)s] that was pointing to [%(t)s]')
                _LOG.warn(msg % {'l': link_path, 't': link_target})
                os.unlink(link_path)

            else:
                msg = _('Link path [%(l)s] exists, but is not a symbolic link')
                raise RuntimeError(msg % {'l': link_path})

        msg = _('Creating symbolic link [%(l)s] pointing to [%(s)s]')
        _LOG.debug(msg % {'l': link_path, 's': source_path})

        os.symlink(source_path, link_path)

    # -- cleanup ---------------------------------------------------------------

    @staticmethod
    def _clear_directory(path):
        """
        Clear out the contents of the given directory.

        :param path: path of the directory to clear out
        :type  path: str
        """

        if not os.path.exists(path):
            return

        for entry in os.listdir(path):

            entry_path = os.path.join(path, entry)

            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)

            elif os.path.isfile(entry_path) or os.path.islink(entry_path):
                os.unlink(entry_path)

