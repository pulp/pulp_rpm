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

from pulp_rpm.common.constants import (
    STATE_NOT_STARTED, STATE_RUNNING, STATE_SKIPPED, STATE_FAILED, STATE_CANCELLED,
    PUBLISH_STEPS, PUBLISH_METADATA_STEP, PROGRESS_STATE_KEY, PROGRESS_TOTAL_KEY,
    PROGRESS_PROCESSED_KEY, PROGRESS_SUCCESSES_KEY, PROGRESS_FAILURES_KEY,
    PROGRESS_ERROR_DETAILS_KEY)

# -- publishing reporting ------------------------------------------------------

PROGRESS_SUB_REPORT = {PROGRESS_STATE_KEY: STATE_RUNNING,
                       PROGRESS_TOTAL_KEY: 0,
                       PROGRESS_PROCESSED_KEY: 0,
                       PROGRESS_SUCCESSES_KEY: 0,
                       PROGRESS_FAILURES_KEY: 0,
                       PROGRESS_ERROR_DETAILS_KEY: []}

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

    return {PROGRESS_STATE_KEY: STATE_NOT_STARTED}


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

    if progress_report[PUBLISH_METADATA_STEP][PROGRESS_STATE_KEY] is STATE_SKIPPED:
        summary[SKIP_METADATA_UPDATE] = True

    for step in PUBLISH_STEPS:

        if progress_report[step][PROGRESS_STATE_KEY] is STATE_FAILED:
            publish_succeeded = False

        if progress_report[step][PROGRESS_STATE_KEY] is STATE_CANCELLED:
            publish_cancelled = True

        total = progress_report[step].get(PROGRESS_TOTAL_KEY, 0)
        processed = progress_report[step].get(PROGRESS_PROCESSED_KEY, 0)
        succeeded = progress_report[step].get(PROGRESS_SUCCESSES_KEY, 0)
        failed = progress_report[step].get(PROGRESS_FAILURES_KEY, 0)

        summary[NUMBER_UNITS_TOTAL % step] = total
        summary[NUMBER_UNITS_PROCESSED % step] = processed
        summary[NUMBER_UNITS_SUCCEEDED % step] = succeeded
        summary[NUMBER_UNITS_FAILED % step] = failed

        details[ERRORS_LIST].extend(progress_report[step].get(PROGRESS_ERROR_DETAILS_KEY, []))

    if publish_succeeded:
        final_report = conduit.build_success_report(summary, details)

    else:
        final_report = conduit.build_failure_report(summary, details)

    final_report.canceled_flag = publish_cancelled

    return final_report

