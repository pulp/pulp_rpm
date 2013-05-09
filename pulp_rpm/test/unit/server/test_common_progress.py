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
The tests in this module test the pulp_rpm.common.progress module.
"""

from datetime import datetime
import unittest

from pulp.common.dateutils import format_iso8601_datetime
import mock

from pulp_rpm.common import progress
import importer_mocks


class TestISOProgressReport(unittest.TestCase):
    """
    Test the ISOProgressReport class.
    """
    def setUp(self):
        self.conduit = importer_mocks.get_sync_conduit()

    def test___init___with_defaults(self):
        """
        Test the __init__ method with all default parameters.
        """
        report = progress.ISOProgressReport(self.conduit)

        # Make sure all the appropriate attributes were set
        self.assertEqual(report.conduit, self.conduit)
        self.assertEqual(report._state, progress.ISOProgressReport.STATE_NOT_STARTED)

        # The state_times attribute should be a dictionary with only the time the not started state was
        # entered
        self.assertTrue(isinstance(report.state_times, dict))
        self.assertEqual(len(report.state_times), 1)
        self.assertTrue(isinstance(report.state_times[progress.ISOProgressReport.STATE_NOT_STARTED],
                                   datetime))

        self.assertEqual(report.num_isos, None)
        self.assertEqual(report.num_isos_finished, 0)
        self.assertEqual(report.iso_error_messages, {})
        self.assertEqual(report.error_message, None)
        self.assertEqual(report.traceback, None)

    def test___init__with_non_defaults(self):
        """
        Test the __init__ method when passing in parameters.
        """
        state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS
        state_times = {progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS: datetime.utcnow()}
        num_isos = 5
        num_isos_finished = 3
        iso_error_messages = {'an.iso': "No!"}
        error_message = 'This is an error message.'
        traceback = 'This is a traceback.'

        report = progress.ISOProgressReport(
            self.conduit, state=state, state_times=state_times, num_isos=num_isos,
            num_isos_finished=num_isos_finished, iso_error_messages=iso_error_messages,
            error_message=error_message, traceback=traceback)

        # Make sure all the appropriate attributes were set
        self.assertEqual(report.conduit, self.conduit)
        self.assertEqual(report._state, state)
        self.assertEqual(report.state_times, state_times)
        self.assertEqual(report.num_isos, num_isos)
        self.assertEqual(report.num_isos_finished, num_isos_finished)
        self.assertEqual(report.iso_error_messages, iso_error_messages)
        self.assertEqual(report.error_message, error_message)
        self.assertEqual(report.traceback, traceback)

    def test_add_failed_iso(self):
        """
        Test the add_failed_iso() method.
        """
        report = progress.ISOProgressReport(self.conduit)
        iso = mock.MagicMock()
        iso.name = 'error.iso'
        error_message = 'error message'

        report.add_failed_iso(iso, error_message)

        self.assertEqual(report.iso_error_messages, {iso.name: error_message})

    def test_build_final_report_failure(self):
        """
        Test build_final_report() when there is a failure.
        """
        report = progress.ISOProgressReport(self.conduit, state=progress.ISOProgressReport.STATE_ISOS_FAILED)

        conduit_report = report.build_final_report()

        # The success report call should not have been made
        self.assertEqual(self.conduit.build_success_report.call_count, 0)
        # We should have called the failure report once with the serialized progress report as the summary
        self.conduit.build_failure_report.assert_called_once_with(report.build_progress_report(), None)

        # Inspect the conduit report
        self.assertEqual(conduit_report.success_flag, False)
        self.assertEqual(conduit_report.canceled_flag, False)
        self.assertEqual(conduit_report.summary, report.build_progress_report())
        self.assertEqual(conduit_report.details, None)

    def test_build_final_report_success(self):
        """
        Test build_final_report() when there is success.
        """
        report = progress.ISOProgressReport(self.conduit, state=progress.ISOProgressReport.STATE_COMPLETE)

        conduit_report = report.build_final_report()

        # The failure report call should not have been made
        self.assertEqual(self.conduit.build_failure_report.call_count, 0)
        # We should have called the success report once with the serialized progress report as the summary
        self.conduit.build_success_report.assert_called_once_with(report.build_progress_report(), None)

        # Inspect the conduit report
        self.assertEqual(conduit_report.success_flag, True)
        self.assertEqual(conduit_report.canceled_flag, False)
        self.assertEqual(conduit_report.summary, report.build_progress_report())
        self.assertEqual(conduit_report.details, None)

    def test_build_progress_report(self):
        """
        Test the build_progress_report() method.
        """
        state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS
        state_times = {progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS: datetime.utcnow()}
        num_isos = 5
        num_isos_finished = 3
        iso_error_messages = {'an.iso': "No!"}
        error_message = 'This is an error message.'
        traceback = 'This is a traceback.'
        report = progress.ISOProgressReport(
            self.conduit, state=state, state_times=state_times, num_isos=num_isos,
            num_isos_finished=num_isos_finished, iso_error_messages=iso_error_messages,
            error_message=error_message, traceback=traceback)

        report = report.build_progress_report()

        # Make sure all the appropriate attributes were set
        self.assertEqual(report['state'], state)
        expected_state_times = {}
        for key, value in state_times.items():
            expected_state_times[key] = format_iso8601_datetime(value)
        self.assertTrue(report['state_times'], expected_state_times)
        self.assertEqual(report['num_isos'], num_isos)
        self.assertEqual(report['num_isos_finished'], num_isos_finished)
        self.assertEqual(report['iso_error_messages'], iso_error_messages)
        self.assertEqual(report['error_message'], error_message)
        self.assertEqual(report['traceback'], traceback)

    def test_from_progress_report(self):
        """
        Test that building an ISOProgressReport from the output of build_progress_report() makes an equivalent
        ISOProgressReport.
        """
        state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS
        state_times = {progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS: datetime(2013, 5, 3, 20, 11, 3)}
        num_isos = 5
        num_isos_finished = 3
        iso_error_messages = {'an.iso': "No!"}
        error_message = 'This is an error message.'
        traceback = 'This is a traceback.'
        original_report = progress.ISOProgressReport(
            self.conduit, state=state, state_times=state_times, num_isos=num_isos,
            num_isos_finished=num_isos_finished, iso_error_messages=iso_error_messages,
            error_message=error_message, traceback=traceback)
        serial_report = original_report.build_progress_report()

        report = progress.ISOProgressReport.from_progress_report(serial_report)

        # All of the values that we had set in the initial report should be identical on this one, except that
        # the conduit should be None
        self.assertEqual(report.conduit, None)
        self.assertEqual(report._state, original_report.state)
        self.assertEqual(report.state_times, original_report.state_times)
        self.assertEqual(report.num_isos, original_report.num_isos)
        self.assertEqual(report.num_isos_finished, original_report.num_isos_finished)
        self.assertEqual(report.iso_error_messages, original_report.iso_error_messages)
        self.assertEqual(report.error_message, original_report.error_message)
        self.assertEqual(report.traceback, original_report.traceback)

    def test_update_progress(self):
        """
        The update_progress() method should send the progress report to the conduit.
        """
        state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS
        state_times = {progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS: datetime.utcnow()}
        num_isos = 5
        num_isos_finished = 3
        iso_error_messages = {'an.iso': "No!"}
        error_message = 'This is an error message.'
        traceback = 'This is a traceback.'
        report = progress.ISOProgressReport(
            self.conduit, state=state, state_times=state_times, num_isos=num_isos,
            num_isos_finished=num_isos_finished, iso_error_messages=iso_error_messages,
            error_message=error_message, traceback=traceback)

        report.update_progress()

        # Make sure the conduit's set_progress() method was called
        self.conduit.set_progress.assert_called_once_with(report.build_progress_report())

    def test__get_state(self):
        """
        Test our state property as a getter.
        """
        report = progress.ISOProgressReport(None, state=progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)

        self.assertEqual(report.state, progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)

    def test__set_state_allowed_transition(self):
        """
        Test the state property as a setter for an allowed state transition.
        """
        report = progress.ISOProgressReport(self.conduit,
                                            state=progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)

        # This is an allowed transition, so it should not raise an error
        report.state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS

        self.assertEqual(report._state, progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS)
        self.assertTrue(report._state in report.state_times)
        self.assertTrue(isinstance(report.state_times[report._state], datetime))
        self.conduit.set_progress.assert_called_once_with(report.build_progress_report())

    def test__set_state_disallowed_transition(self):
        """
        Test the state property as a setter for a disallowed state transition.
        """
        report = progress.ISOProgressReport(None, state=progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)

        # We can't go from STATE_MANIFEST_IN_PROGRESS to STATE_COMPLETE
        try:
            report.state = progress.ISOProgressReport.STATE_COMPLETE
            self.fail('The line above this should have raised an Exception, but it did not.')
        except ValueError, e:
            expected_error_substring = '%s --> %s' % (report.state, progress.ISOProgressReport.STATE_COMPLETE)
            self.assertTrue(expected_error_substring in str(e))

        # The state should remain the same
        self.assertEqual(report.state, progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)
        self.assertTrue(progress.ISOProgressReport.STATE_COMPLETE not in report.state_times)

    def test__set_state_iso_errors(self):
        """
        Test the state property as a setter for the situation when the state is marked as COMPLETE, but there
        are ISO errors. It should automatically get set to ISOS_FAILED instead.
        """
        report = progress.ISOProgressReport(self.conduit, iso_error_messages={'iso': 'error'},
                                            state=progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS)

        # This should trigger an automatic STATE_FAILED, since there are ISO errors
        report.state = progress.ISOProgressReport.STATE_COMPLETE

        self.assertEqual(report._state, progress.ISOProgressReport.STATE_ISOS_FAILED)
        self.assertTrue(report._state in report.state_times)
        self.assertTrue(isinstance(report.state_times[report._state], datetime))
        self.assertTrue(progress.ISOProgressReport.STATE_COMPLETE not in report.state_times)
        self.conduit.set_progress.assert_called_once_with(report.build_progress_report())

    def test__set_state_same_state(self):
        """
        Test setting a state to the same state. This is weird, but allowed.
        """
        report = progress.ISOProgressReport(None, state=progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)

        # This should not raise an Exception
        report.state = progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS

        self.assertEqual(report.state, progress.ISOProgressReport.STATE_MANIFEST_IN_PROGRESS)


class TestSyncProgressReport(unittest.TestCase):
    """
    Test the SyncProgressReport class.
    """
    def setUp(self):
        self.conduit = importer_mocks.get_sync_conduit()

    def test___init__with_non_defaults(self):
        """
        Test the __init__ method when passing in parameters.
        """
        state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS
        state_times = {progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS: datetime.utcnow()}
        num_isos = 5
        num_isos_finished = 3
        iso_error_messages = {'an.iso': "No!"}
        error_message = 'This is an error message.'
        traceback = 'This is a traceback.'
        total_bytes = 1024
        finished_bytes = 512

        report = progress.SyncProgressReport(
            self.conduit, state=state, state_times=state_times, num_isos=num_isos,
            num_isos_finished=num_isos_finished, iso_error_messages=iso_error_messages,
            error_message=error_message, traceback=traceback, total_bytes=total_bytes,
            finished_bytes=finished_bytes)

        # Make sure all the appropriate attributes were set
        self.assertEqual(report.conduit, self.conduit)
        self.assertEqual(report._state, state)
        self.assertEqual(report.state_times, state_times)
        self.assertEqual(report.num_isos, num_isos)
        self.assertEqual(report.num_isos_finished, num_isos_finished)
        self.assertEqual(report.iso_error_messages, iso_error_messages)
        self.assertEqual(report.error_message, error_message)
        self.assertEqual(report.traceback, traceback)
        self.assertEqual(report.total_bytes, total_bytes)
        self.assertEqual(report.finished_bytes, finished_bytes)

    def test_build_progress_report(self):
        """
        Test the build_progress_report() method.
        """
        state = progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS
        state_times = {progress.ISOProgressReport.STATE_ISOS_IN_PROGRESS: datetime.utcnow()}
        num_isos = 5
        num_isos_finished = 3
        iso_error_messages = {'an.iso': "No!"}
        error_message = 'This is an error message.'
        traceback = 'This is a traceback.'
        total_bytes = 1024
        finished_bytes = 512
        report = progress.SyncProgressReport(
            self.conduit, state=state, state_times=state_times, num_isos=num_isos,
            num_isos_finished=num_isos_finished, iso_error_messages=iso_error_messages,
            error_message=error_message, traceback=traceback, total_bytes=total_bytes,
            finished_bytes=finished_bytes)

        report = report.build_progress_report()

        # Make sure all the appropriate attributes were set
        self.assertEqual(report['state'], state)
        expected_state_times = {}
        for key, value in state_times.items():
            expected_state_times[key] = format_iso8601_datetime(value)
        self.assertTrue(report['state_times'], expected_state_times)
        self.assertEqual(report['num_isos'], num_isos)
        self.assertEqual(report['num_isos_finished'], num_isos_finished)
        self.assertEqual(report['iso_error_messages'], iso_error_messages)
        self.assertEqual(report['error_message'], error_message)
        self.assertEqual(report['traceback'], traceback)
        self.assertEqual(report['total_bytes'], total_bytes)
        self.assertEqual(report['finished_bytes'], finished_bytes)