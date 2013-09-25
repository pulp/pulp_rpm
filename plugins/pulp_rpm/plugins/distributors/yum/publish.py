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

from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common.ids import (
    TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO, TYPE_ID_YUM_REPO_METADATA_FILE)

from . import configuration

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
PUBLISH_FINISHED_STATED = 'FINISHED'
PUBLISH_FAILED_STATE = 'FAILED'
PUBLISH_CANCELED_STATE = 'CANCELED'

PUBLISH_STATES = (PUBLISH_NOT_STARTED_STATE, PUBLISH_IN_PROGRESS_STATE, PUBLISH_SKIPPED_STATE,
                  PUBLISH_FINISHED_STATED, PUBLISH_FAILED_STATE, PUBLISH_CANCELED_STATE)

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

# -- package fields ------------------------------------------------------------

PACKAGE_FIELDS = ['id', 'name', 'version', 'release', 'arch', 'epoch',
                  '_storage_path', 'checksum', 'checksum_type'] # XXX actually 'checksumtype', so change it!

# -- publisher class -----------------------------------------------------------

class Publisher(object):

    def __init__(self, repo, publish_conduit, config):

        self.repo = repo
        self.conduit = publish_conduit
        self.config = config

        self.progress_report = copy.deepcopy(PROGRESS_REPORT)
        self.canceled = False

    @property
    def skip_list(self):
        return self.config.get('skip', [])

    # -- publish api methods ---------------------------------------------------

    def publish(self):
        pass

    def cancel(self):

        self.canceled = True

        # put the reporting logic here so I don't have to put it everywhere
        for step, sub_report in self.progress_report.items():
            if sub_report[STATE] is PUBLISH_IN_PROGRESS_STATE:
                self.progress_report[step][STATE] = PUBLISH_CANCELED_STATE

    # -- publish helper methods ------------------------------------------------

    def _publish_rpms(self): # and srpms too

        if self.canceled:
            return

        if TYPE_ID_RPM in self.skip_list:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_RPMS_STEP)

        # XXX memory concerns here, this should return something akin to a db
        # cursor or a generator, but it probably returns a list
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_RPM, TYPE_ID_SRPM],
                                           unit_fields=PACKAGE_FIELDS)

        units = self.conduit.get_units(criteria=criteria)

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

        self._init_step_progress_report(PUBLISH_PACKAGE_CATEGORIES_STEP)

    def _publish_distribution(self):

        if self.canceled:
            return

        self._init_step_progress_report(PUBLISH_DISTRIBUTION_STEP)

    def _publish_metadata(self):

        if self.canceled:
            return

        self._init_step_progress_report(PUBLISH_METADATA_STEP)

    def _publish_over_http(self):

        if self.canceled:
            return

        self._init_step_progress_report(PUBLISH_OVER_HTTP_STEP)

    def _publish_over_https(self):

        if self.canceled:
            return

        self._init_step_progress_report(PUBLISH_OVER_HTTPS_STEP)

    # -- progress methods ------------------------------------------------------

    def _init_step_progress_report(self, step):
        assert step in PUBLISH_STEPS

        self.progress_report[step] = copy.deepcopy(PROGRESS_SUB_REPORT)

    def _report_progress(self, step, **report_details):
        assert step in PUBLISH_STEPS
        assert set(report_details).issubset(set(PUBLISH_REPORT_KEYWORDS))

        self.progress_report[step].update(report_details)
        self.conduit.set_progress(self.progress_report)

