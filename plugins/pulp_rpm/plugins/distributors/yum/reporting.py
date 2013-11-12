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

PROGRESS_SUB_REPORT = {STATE: PUBLISH_IN_PROGRESS_STATE,
                       TOTAL: 0,
                       PROCESSED: 0,
                       SUCCESSES: 0,
                       FAILURES: 0,
                       ERROR_DETAILS: []}

# -- final reporting -----------------------------------------------------------

NUMBER_UNITS_TOTAL = 'number %s units total'
NUMBER_UNITS_PROCESSED = 'number %s units processed'
NUMBER_UNITS_SUCCEEDED = 'number %s units succeeded'
NUMBER_UNITS_FAILED = 'number %s units failed'

RELATIVE_PATH = 'relative_path'
SKIP_METADATA_UPDATE = 'skip_metadata_update'

SUMMARY_REPORT = {RELATIVE_PATH: None,
                  SKIP_METADATA_UPDATE: False}

ERRORS_LIST = 'errors'
METADATA_GENERATION_TIME = 'time_metadata_sec'

DETAILS_REPORT = {ERRORS_LIST: [],
                  METADATA_GENERATION_TIME: 0}

# -- api -----------------------------------------------------------------------

def new_progress_sub_report():
    """
    :return: new progress sub-report
    :rtype:  dict
    """

    return {STATE: PUBLISH_NOT_STARTED_STATE}


def initialize_progress_sub_report(report):
    """
    Initialize an existing progress sub-report.

    :param report: sub-report to initialize
    :type  report: dict
    """

    report.update(copy.deepcopy(PROGRESS_SUB_REPORT))


def new_progress_report():
    """
    :return: new progress report dictionary
    :rtype:  dict
    """

    return dict((step, new_progress_sub_report()) for step in PUBLISH_STEPS)


def build_final_report(conduit, relative_path, progress_report):
    """
    :type conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
    :type relative_path: basestring
    :type progress_report: dict
    :rtype: pulp.plugins.model.PublishReport
    """

    publish_succeeded = True
    publish_cancelled = False

    summary = copy.deepcopy(SUMMARY_REPORT)
    details = copy.deepcopy(DETAILS_REPORT)

    summary[RELATIVE_PATH] = relative_path

    if progress_report[PUBLISH_METADATA_STEP][STATE] is PUBLISH_SKIPPED_STATE:
        summary[SKIP_METADATA_UPDATE] = True

    for step in PUBLISH_STEPS:

        if progress_report[step][STATE] is PUBLISH_FAILED_STATE:
            publish_succeeded = False

        if progress_report[step][STATE] is PUBLISH_CANCELED_STATE:
            publish_succeeded = True

        total = progress_report[step].get(TOTAL, 0)
        processed = progress_report[step].get(PROCESSED, 0)
        succeeded = progress_report[step].get(SUCCESSES, 0)
        failed = progress_report[step].get(FAILURES, 0)

        summary[NUMBER_UNITS_TOTAL % step] = total
        summary[NUMBER_UNITS_PROCESSED % step] = processed
        summary[NUMBER_UNITS_SUCCEEDED % step] = succeeded
        summary[NUMBER_UNITS_FAILED % step] = failed

        details[ERRORS_LIST].extend(progress_report[step].get(ERROR_DETAILS, []))

    if publish_succeeded:
        final_report = conduit.build_success_report(summary, details)

    else:
        final_report = conduit.build_failure_report(summary, details)

    final_report.canceled_flag = publish_cancelled

    return final_report

