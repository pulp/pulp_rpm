# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
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
importer and distributor.
"""
from datetime import datetime

from pulp_rpm.common import reporting
from pulp_rpm.common.constants import STATE_COMPLETE, STATE_FAILED, STATE_NOT_STARTED, STATE_RUNNING


class ISOProgressReport(object):
    def __init__(self, conduit):
        self.conduit = conduit

        # These variables track the state of the ISO download stage
        self._isos_state = STATE_NOT_STARTED
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

        # Manifest download and generation
        self._manifest_state = STATE_NOT_STARTED
        self.manifest_execution_time = None
        self.manifest_error_message = None
        self.manifest_exception = None
        self.manifest_traceback = None

    def add_failed_iso(self, iso, error_report):
        """
        Updates the progress report that a iso failed to be imported.
        """
        self.isos_error_count += 1
        self.isos_individual_errors[iso['name']] = {
            'error_report': error_report,
        }

    def build_progress_report(self):
        """
        Returns the actual report that should be sent to Pulp as the current
        progress of the sync.

        :return: description of the current state of the sync
        :rtype:  dict
        """

        report = {
            'manifest': self._generate_manifest_section(),
            'isos': self._generate_isos_section(),
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
        :rtype:  SyncProgressReport
        """

        r = cls(None)

        m = report['manifest']
        r.manifest_state = m['state']
        r.manifest_execution_time = m['execution_time']
        r.manifest_error_message = m['error_message']
        r.manifest_exception = m['error']
        r.manifest_traceback = m['traceback']

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

    def _get_isos_state(self):
        return self._isos_state

    def _set_isos_state(self, new_state):
        self._set_timed_state('_isos_state', '_isos_start_time', 'isos_execution_time', new_state)

    isos_state = property(_get_isos_state, _set_isos_state)

    def _get_manifest_state(self):
        return self._manifest_state

    def _set_manifest_state(self, new_state):
        self._set_timed_state('_manifest_state', '_manifest_start_time', 'manifest_execution_time', new_state)

    manifest_state = property(_get_manifest_state, _set_manifest_state)

    def update_progress(self):
        """
        Sends the current state of the progress report to Pulp.
        """
        report = self.build_progress_report()
        self.conduit.set_progress(report)

    def _generate_isos_section(self):
        isos_report = {
            'state': self.isos_state,
            'execution_time': self.isos_execution_time,
            'total_count': self.isos_total_count,
            'finished_count': self.isos_finished_count,
            'error_count': self.isos_error_count,
            'individual_errors': self.isos_individual_errors,
            'error_message': self.isos_error_message,
            'error': reporting.format_exception(self.isos_exception),
            'traceback': reporting.format_traceback(self.isos_traceback),
        }
        return isos_report

    def _generate_manifest_section(self):
        manifest_report = {
            'state': self.manifest_state,
            'execution_time': self.manifest_execution_time,
            'error_message': self.manifest_error_message,
            'error': reporting.format_exception(self.manifest_exception),
            'traceback': reporting.format_traceback(self.manifest_traceback),
        }
        return manifest_report

    def _set_timed_state(self, state_attribute_name, start_time_attribute_name, execution_time_attribute_name,
                         new_state):
        """
        For the manifest_state and isos_state attributes, we have special setter properties that also time
        how long it takes them to move from a running state to a complete or failed state. This method is used
        by both of those properties to keep track of how long the state transition takes, and it also sets the
        appropriate state on the progress report.

        :param state_attribute_name:          The name of the attribute on self where the new state should be
                                              stored
        :type  state_attribute_name:          basestring
        :param start_time_attribute_name:     The name of an attribute on self that should be used to store
                                              the time when the attribute entered a running state.
        :type  start_time_attribute_name:     basestring
        :param execution_time_attribute_name: The name of an attribute on self that should be used to store
                                              the calculated execution time.
        :type  execution_time_attribute_name: basestring
        :param new_state:                     The new state that should be set onto self.state_attribute_name
        :type  new_state:                     basestring
        """
        current_state = getattr(self, state_attribute_name)
        if current_state == STATE_NOT_STARTED and new_state == STATE_RUNNING:
            setattr(self, start_time_attribute_name, datetime.utcnow())

        if current_state == STATE_RUNNING and new_state in [STATE_COMPLETE, STATE_FAILED]:
            execution_time = datetime.utcnow() - getattr(self, start_time_attribute_name)
            execution_time = (execution_time.days * 3600 * 24) + \
                             execution_time.seconds
            setattr(self, execution_time_attribute_name, execution_time)

        setattr(self, state_attribute_name, new_state)


class PublishProgressReport(ISOProgressReport):
    """
    Used to carry the state of the publish run as it proceeds. This object is used
    to update the on going progress in Pulp at appropriate intervals through
    the update_progress call. Once the publish is finished, this object should
    be used to produce the final report to return to Pulp to describe the
    result of the operation.
    """
    def __init__(self, conduit):
        super(self.__class__, self).__init__(conduit)

        # Publishing state
        self.publish_http = STATE_NOT_STARTED
        self.publish_https = STATE_NOT_STARTED

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
        report = super(self.__class__, self).build_progress_report()
        report['publishing'] = self._generate_publishing_section()
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
        r = super(cls).from_progress_dict(report)

        m = report['publishing']
        r.publish_http = m['http']
        r.publish_https = m['https']

        return r

    def _generate_publishing_section(self):
        publishing_report = {
            'http': self.publish_http,
            'https': self.publish_https,
        }
        return publishing_report


class SyncProgressReport(ISOProgressReport):
    """
    Used to carry the state of the sync run as it proceeds. This object is used
    to update the on going progress in Pulp at appropriate intervals through
    the update_progress call. Once the sync is finished, this object should
    be used to produce the final report to return to Pulp to describe the
    sync.
    """
    def __init__(self, conduit):
        super(self.__class__, self).__init__(conduit)

        # Let's also track how many bytes we've got on the ISOs
        self.isos_total_bytes = None
        self.isos_finished_bytes = 0

    def build_final_report(self):
        """
        Assembles the final report to return to Pulp at the end of the sync.
        The conduit will include information that it has tracked over the
        course of its usage, therefore this call should only be invoked
        when it is time to return the report.
        """
        if self.isos_error_count != 0:
            self.isos_state = STATE_FAILED

        # Report fields
        total_execution_time = -1
        if self.manifest_execution_time is not None and self.isos_execution_time is not None:
            total_execution_time = self.manifest_execution_time + self.isos_execution_time

        summary = {
            'total_execution_time': total_execution_time
        }

        details = {
            'total_count': self.isos_total_count,
            'finished_count': self.isos_finished_count,
            'error_count': self.isos_error_count,
        }

        # Determine if the report was successful or failed
        all_step_states = (self.manifest_state, self.isos_state)
        unsuccessful_steps = [s for s in all_step_states if s != STATE_COMPLETE]

        if len(unsuccessful_steps) == 0:
            report = self.conduit.build_success_report(summary, details)
        else:
            report = self.conduit.build_failure_report(summary, details)

        return report

    def _generate_isos_section(self):
        isos_report = super(self.__class__, self)._generate_isos_section()
        isos_report['total_bytes'] = self.isos_total_bytes
        isos_report['finished_bytes'] = self.isos_finished_bytes
        return isos_report