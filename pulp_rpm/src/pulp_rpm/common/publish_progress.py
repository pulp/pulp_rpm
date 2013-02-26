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
Contains classes and functions related to tracking the progress of an ISO distributor.
"""

from pulp_rpm.common.constants import STATE_COMPLETE, STATE_FAILED, STATE_NOT_STARTED


class PublishProgressReport(object):
    """
    Used to carry the state of the publish run as it proceeds. This object is used
    to update the on going progress in Pulp at appropriate intervals through
    the update_progress call. Once the publish is finished, this object should
    be used to produce the final report to return to Pulp to describe the
    result of the operation.
    """

    def __init__(self, conduit):
        self.conduit = conduit

        # Modules symlink step
        self.isos_state = STATE_NOT_STARTED
        self.isos_execution_time = None
        self.isos_total_count = None
        self.isos_finished_count = 0
        self.isos_error_count = 0
        # mapping of iso to its error
        self.isos_individual_errors = {}
        # overall execution error
        self.isos_error_message = None
        self.isos_exception = None
        self.isos_traceback = None

        # Manifest generation
        self.manifest_state = STATE_NOT_STARTED
        self.manifest_execution_time = None
        self.manifest_error_message = None
        self.manifest_exception = None
        self.manifest_traceback = None

        # Publishing
        self.publish_http = STATE_NOT_STARTED
        self.publish_https = STATE_NOT_STARTED

    def add_failed_iso(self, unit, error_message):
        """
        Updates the progress report that a iso failed to be built to the
        repository.

        :param unit: Pulp representation of the iso
        :type  unit: pulp.plugins.model.AssociatedUnit
        """
        self.isos_error_count += 1
        self.isos_individual_errors[unit.unit_key['name']] = error_message

    def build_final_report(self):
        """
        Assembles the final report to return to Pulp at the end of the run.

        :return: report to return to Pulp at the end of the publish call
        :rtype:  pulp.plugins.model.PublishReport
        """

        # Report fields
        total_execution_time = -1
        if self.manifest_execution_time is not None and self.isos_execution_time is not None:
            total_execution_time = self.manifest_execution_time + self.isos_execution_time

        summary = {
            'total_execution_time': total_execution_time
        }

        # intentionally empty; not sure what to put in here
        details = {}

        # Determine if the report was successful or failed
        all_step_states = (self.manifest_state, self.isos_state, self.publish_http,
                           self.publish_https)
        unsuccessful_steps = [s for s in all_step_states if s != STATE_COMPLETE]

        if len(unsuccessful_steps) == 0:
            report = self.conduit.build_success_report(summary, details)
        else:
            report = self.conduit.build_failure_report(summary, details)

        return report

    def build_progress_report(self):
        """
        Returns the actual report that should be sent to Pulp as the current
        progress of the publish.

        :return: description of the current state of the publish
        :rtype:  dict
        """

        report = {
            'isos': self._isos_section(),
            'manifest': self._manifest_section(),
            'publishing': self._publishing_section(),
        }
        return report

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
        :rtype:  PublishProgressReport
        """

        r = cls(None)

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

        m = report['manifest']
        r.manifest_state = m['state']
        r.manifest_execution_time = m['execution_time']
        r.manifest_error_message = m['error_message']
        r.manifest_exception = m['error']
        r.manifest_traceback = m['traceback']

        m = report['publishing']
        r.publish_http = m['http']
        r.publish_https = m['https']

        return r

    def update_progress(self):
        """
        Sends the current state of the progress report to Pulp.
        """
        report = self.build_progress_report()
        self.conduit.set_progress(report)

    def _isos_section(self):
        isos_report = {
            'state': self.isos_state,
            'execution_time': self.isos_execution_time,
            'total_count': self.isos_total_count,
            'finished_count': self.isos_finished_count,
            'error_count': self.isos_error_count,
            'individual_errors': self.isos_individual_errors,
            'error_message': self.isos_error_message
        }
        return isos_report

    def _manifest_section(self):
        manifest_report = {
            'state': self.manifest_state,
            'execution_time': self.manifest_execution_time,
            'error_message': self.manifest_error_message,
            }
        return manifest_report

    def _publishing_section(self):
        publishing_report = {
            'http': self.publish_http,
            'https': self.publish_https,
        }
        return publishing_report