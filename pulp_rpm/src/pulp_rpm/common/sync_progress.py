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
"""
Contains classes and functions related to tracking the progress of the ISO
importer.
"""
from pulp_rpm.common import reporting
from pulp_rpm.common.constants import STATE_COMPLETE, STATE_FAILED, STATE_NOT_STARTED


class SyncProgressReport(object):
    """
    Used to carry the state of the sync run as it proceeds. This object is used
    to update the on going progress in Pulp at appropriate intervals through
    the update_progress call. Once the sync is finished, this object should
    be used to produce the final report to return to Pulp to describe the
    sync.
    """

    @classmethod
    def from_progress_dict(cls, report):
        """
        Parses the output from the build_progress_report method into an instance
        of this class. The intention is to use this client-side to reconstruct
        the instance as it is retrieved from the server.

        The build_final_report call on instances returned from this call will
        not function as it requires the server-side conduit to be provided.
        Additionally, any exceptions and tracebacks will be a text representation
        instead of formal objects.

        :param report: progress report retrieved from the server's task
        :type  report: dict
        :return: instance populated with the state in the report
        :rtype:  SyncProgressReport
        """

        r = cls(None)

        m = report['metadata']
        r.metadata_state = m['state']
        r.metadata_execution_time = m['execution_time']
        r.metadata_current_query = m['current_query']
        r.metadata_query_finished_count = m['query_finished_count']
        r.metadata_query_total_count = m['query_total_count']
        r.metadata_error_message = m['error_message']
        r.metadata_exception = m['error']
        r.metadata_traceback = m['traceback']

        m = report['isos']
        r.isos_state = m['state']
        r.isos_execution_time = m['execution_time']
        r.isos_total_count = m['total_count']
        r.isos_finished_count = m['finished_count']
        r.isos_error_count = m['error_count']
        r.isos_individual_errors = m['individual_errors']
        r.isos_error_message = m['error_message']
        r.isos_exception = m['error']
        r.isos_traceback = m['traceback']

        return r

    def __init__(self, conduit):
        self.conduit = conduit

        # Metadata download & parsing
        self.metadata_state = STATE_NOT_STARTED
        self.metadata_query_finished_count = None
        self.metadata_query_total_count = None
        self.metadata_current_query = None
        self.metadata_execution_time = None
        self.metadata_error_message = None
        self.metadata_exception = None
        self.metadata_traceback = None

        # ISO download
        self.isos_state = STATE_NOT_STARTED
        self.isos_execution_time = None
        self.isos_total_count = None
        self.isos_finished_count = None
        self.isos_error_count = None
        self.isos_individual_errors = None # mapping of iso to its error
        self.isos_error_message = None # overall execution error
        self.isos_exception = None
        self.isos_traceback = None

    # -- public methods -------------------------------------------------------

    def update_progress(self):
        """
        Sends the current state of the progress report to Pulp.
        """
        report = self.build_progress_report()
        self.conduit.set_progress(report)

    def build_final_report(self):
        """
        Assembles the final report to return to Pulp at the end of the sync.
        The conduit will include information that it has tracked over the
        course of its usage, therefore this call should only be invoked
        when it is time to return the report.
        """

        # Report fields
        total_execution_time = -1
        if self.metadata_execution_time is not None and self.isos_execution_time is not None:
            total_execution_time = self.metadata_execution_time + self.isos_execution_time

        summary = {
            'total_execution_time' : total_execution_time
        }

        details = {
            'total_count' : self.isos_total_count,
            'finished_count' : self.isos_finished_count,
            'error_count' : self.isos_error_count,
        }

        # Determine if the report was successful or failed
        all_step_states = (self.metadata_state, self.isos_state)
        unsuccessful_steps = [s for s in all_step_states if s != STATE_COMPLETE]

        if len(unsuccessful_steps) == 0:
            report = self.conduit.build_success_report(summary, details)
        else:
            report = self.conduit.build_failure_report(summary, details)

        return report

    def build_progress_report(self):
        """
        Returns the actual report that should be sent to Pulp as the current
        progress of the sync.

        :return: description of the current state of the sync
        :rtype:  dict
        """

        report = {
            'metadata' : self._metadata_section(),
            'isos'  : self._isos_section(),
        }
        return report

    def add_failed_iso(self, iso, exception, traceback):
        """
        Updates the progress report that a iso failed to be imported.
        """
        self.isos_error_count += 1
        self.isos_individual_errors = self.isos_individual_errors or {}
        error_key = '%s-%s-%s' % (iso.name, iso.version, iso.author)
        self.isos_individual_errors[error_key] = {
            'exception' : reporting.format_exception(exception),
            'traceback' : reporting.format_traceback(traceback),
        }

    # -- report creation methods ----------------------------------------------

    def _metadata_section(self):
        metadata_report = {
            'state' : self.metadata_state,
            'execution_time' : self.metadata_execution_time,
            'current_query' : self.metadata_current_query,
            'query_finished_count' : self.metadata_query_finished_count,
            'query_total_count' : self.metadata_query_total_count,
            'error_message' : self.metadata_error_message,
            'error' : reporting.format_exception(self.metadata_exception),
            'traceback' : reporting.format_traceback(self.metadata_traceback),
        }
        return metadata_report

    def _isos_section(self):
        isos_report = {
            'state' : self.isos_state,
            'execution_time' : self.isos_execution_time,
            'total_count' : self.isos_total_count,
            'finished_count' : self.isos_finished_count,
            'error_count' : self.isos_error_count,
            'individual_errors' : self.isos_individual_errors,
            'error_message' : self.isos_error_message,
            'error' : reporting.format_exception(self.isos_exception),
            'traceback' : reporting.format_traceback(self.isos_traceback),
        }
        return isos_report
