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

from datetime import datetime
import mock
import unittest

from pulp.client.extensions.core import ClientContext, PulpPrompt

from pulp_rpm.common import ids, progress
from pulp_rpm.extension.admin.iso import status


class TestISOStatusRenderer(unittest.TestCase):
    def setUp(self):
        self.context = mock.MagicMock(spec=ClientContext)
        self.context.prompt = mock.MagicMock(spec=PulpPrompt)

    def test___init__(self):
        """
        Test the ISOStatusRenderer.__init__() method.
        """
        renderer = status.ISOStatusRenderer(self.context)

        self.assertEqual(renderer._sync_state, progress.ISOProgressReport.STATE_NOT_STARTED)
        self.context.prompt.create_progress_bar.assert_called_once_with()

    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_publish_report',
                side_effect=status.ISOStatusRenderer._display_publish_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_manifest_sync_report',
                       side_effect=status.ISOStatusRenderer._display_manifest_sync_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_iso_sync_report',
                side_effect=status.ISOStatusRenderer._display_iso_sync_report, autospec=True)
    def test_display_report(self, _display_iso_sync_report, _display_manifest_sync_report,
                            _display_publish_report):
        """
        Test the ISOStatusRenderer.display_report() method.
        """
        progress_report = {
            ids.TYPE_ID_IMPORTER_ISO: {u'traceback': None, u'error_message': None,
                                       u'finished_bytes': 0, u'num_isos': None,
                                       u'state': u'manifest_in_progress', u'total_bytes': None,
                                       u'state_times': {u'not_started': u'2013-04-30T20:37:25',
                                                        u'manifest_in_progress': u'2013-04-30T20:37:25'},
                                       u'num_isos_finished': 0, u'iso_error_messages': {}},
            ids.TYPE_ID_DISTRIBUTOR_ISO: {u'traceback': None, u'error_message': None,
                                          u'num_isos': None, u'state': u'isos_in_progress',
                                          u'state_times': {
                                            u'not_started': u'2013-04-30T20:37:25',
                                            u'manifest_in_progress': u'2013-04-30T20:37:25',
                                            u'isos_in_progress': u'2013-04-30T20:39:53'},
                                          u'num_isos_finished': 0, u'iso_error_messages': {}}}
        renderer = status.ISOStatusRenderer(self.context)

        renderer.display_report(progress_report)

        # All three output methods should have been called with the appropriately instantiates reports objects
        self.assertEqual(_display_iso_sync_report.call_count, 1)
        self.assertEqual(type(_display_iso_sync_report.mock_calls[0][1][1]), progress.SyncProgressReport)
        self.assertEqual(_display_iso_sync_report.mock_calls[0][1][1].state,
                         progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS)

        self.assertEqual(_display_manifest_sync_report.call_count, 1)
        self.assertEqual(type(_display_iso_sync_report.mock_calls[0][1][1]), progress.SyncProgressReport)
        self.assertEqual(_display_iso_sync_report.mock_calls[0][1][1].state,
                         progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS)

        self.assertEqual(_display_publish_report.call_count, 1)
        self.assertEqual(type(_display_publish_report.mock_calls[0][1][1]), progress.PublishProgressReport)
        self.assertEqual(_display_publish_report.mock_calls[0][1][1].state,
                         progress.PublishProgressReport.STATE_ISOS_IN_PROGRESS)

    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_publish_report',
                side_effect=status.ISOStatusRenderer._display_publish_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_manifest_sync_report',
                       side_effect=status.ISOStatusRenderer._display_manifest_sync_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_iso_sync_report',
                side_effect=status.ISOStatusRenderer._display_iso_sync_report, autospec=True)
    def test_display_report_cancelled_sync(self, _display_iso_sync_report, _display_manifest_sync_report,
                            _display_publish_report):
        """
        Test the ISOStatusRenderer.display_report() method when a sync is cancelled.
        """
        progress_report = {
            ids.TYPE_ID_IMPORTER_ISO: {u'traceback': None, u'error_message': None,
                                       u'finished_bytes': 0, u'num_isos': None,
                                       u'state': progress.SyncProgressReport.STATE_CANCELLED,
                                       u'total_bytes': None,
                                       u'state_times': {u'not_started': u'2013-04-30T20:37:25',
                                                        u'manifest_in_progress': u'2013-04-30T20:37:25'},
                                       u'num_isos_finished': 0, u'iso_error_messages': {}},
            ids.TYPE_ID_DISTRIBUTOR_ISO: {u'traceback': None, u'error_message': None,
                                          u'num_isos': None, u'state': u'isos_in_progress',
                                          u'state_times': {
                                            u'not_started': u'2013-04-30T20:37:25',
                                            u'manifest_in_progress': u'2013-04-30T20:37:25',
                                            u'isos_in_progress': u'2013-04-30T20:39:53'},
                                          u'num_isos_finished': 0, u'iso_error_messages': {}}}
        renderer = status.ISOStatusRenderer(self.context)

        renderer.display_report(progress_report)

        # All three output methods should have been called with the appropriately instantiates reports objects
        self.assertEqual(_display_iso_sync_report.call_count, 1)
        self.assertEqual(type(_display_iso_sync_report.mock_calls[0][1][1]), progress.SyncProgressReport)
        self.assertEqual(_display_iso_sync_report.mock_calls[0][1][1].state,
                         progress.SyncProgressReport.STATE_CANCELLED)

        self.assertEqual(_display_manifest_sync_report.call_count, 1)
        self.assertEqual(type(_display_iso_sync_report.mock_calls[0][1][1]), progress.SyncProgressReport)
        self.assertEqual(_display_iso_sync_report.mock_calls[0][1][1].state,
                         progress.SyncProgressReport.STATE_CANCELLED)

        self.assertEqual(_display_publish_report.call_count, 1)
        self.assertEqual(type(_display_publish_report.mock_calls[0][1][1]), progress.PublishProgressReport)
        self.assertEqual(_display_publish_report.mock_calls[0][1][1].state,
                         progress.PublishProgressReport.STATE_ISOS_IN_PROGRESS)

        # A message should have been rendered to the user about the cancellation
        self.assertEqual(renderer.prompt.render_failure_message.call_count, 1)
        self.assertEqual(renderer.prompt.render_failure_message.mock_calls[0][2]['tag'], 'cancelled')

    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_publish_report',
                side_effect=status.ISOStatusRenderer._display_publish_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_manifest_sync_report',
                side_effect=status.ISOStatusRenderer._display_manifest_sync_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_iso_sync_report',
                side_effect=status.ISOStatusRenderer._display_iso_sync_report, autospec=True)
    def test_display_report_no_importer_or_distributor(self, _display_iso_sync_report,
                                                       _display_manifest_sync_report,
                                                       _display_publish_report):
        """
        When there is not an importer or a distributor passed, none of the display functions should be called.
        """
        progress_report = {}
        renderer = status.ISOStatusRenderer(self.context)

        renderer.display_report(progress_report)

        # None of the methods should have been called
        self.assertEqual(_display_iso_sync_report.call_count, 0)
        self.assertEqual(_display_manifest_sync_report.call_count, 0)
        self.assertEqual(_display_publish_report.call_count, 0)

    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_publish_report',
                side_effect=status.ISOStatusRenderer._display_publish_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_manifest_sync_report',
                       side_effect=status.ISOStatusRenderer._display_manifest_sync_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_iso_sync_report',
                side_effect=status.ISOStatusRenderer._display_iso_sync_report, autospec=True)
    def test_display_report_only_distributor(self, _display_iso_sync_report, _display_manifest_sync_report,
                            _display_publish_report):
        """
        When only the distributor is passed, only the publishing section should be called.
        """
        progress_report = {
            ids.TYPE_ID_DISTRIBUTOR_ISO: {u'traceback': None, u'error_message': None,
                                          u'num_isos': None, u'state': u'isos_in_progress',
                                          u'state_times': {
                                            u'not_started': u'2013-04-30T20:37:25',
                                            u'manifest_in_progress': u'2013-04-30T20:37:25',
                                            u'isos_in_progress': u'2013-04-30T20:39:53'},
                                          u'num_isos_finished': 0, u'iso_error_messages': {}}}
        renderer = status.ISOStatusRenderer(self.context)

        renderer.display_report(progress_report)

        # The sync related method should not have been called
        self.assertEqual(_display_iso_sync_report.call_count, 0)
        self.assertEqual(_display_manifest_sync_report.call_count, 0)

        # The publish reporting method should have been called
        self.assertEqual(_display_publish_report.call_count, 1)
        self.assertEqual(type(_display_publish_report.mock_calls[0][1][1]), progress.PublishProgressReport)
        self.assertEqual(_display_publish_report.mock_calls[0][1][1].state,
                         progress.PublishProgressReport.STATE_ISOS_IN_PROGRESS)

    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_publish_report',
                side_effect=status.ISOStatusRenderer._display_publish_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_manifest_sync_report',
                       side_effect=status.ISOStatusRenderer._display_manifest_sync_report, autospec=True)
    @mock.patch('pulp_rpm.extension.admin.iso.status.ISOStatusRenderer._display_iso_sync_report',
                side_effect=status.ISOStatusRenderer._display_iso_sync_report, autospec=True)
    def test_display_report_only_importer(self, _display_iso_sync_report, _display_manifest_sync_report,
                            _display_publish_report):
        """
        When only the importer is passed, only the sync section should be called.
        """
        progress_report = {
            ids.TYPE_ID_IMPORTER_ISO: {u'traceback': None, u'error_message': None,
                                       u'finished_bytes': 0, u'num_isos': None,
                                       u'state': u'not_started', u'total_bytes': None,
                                       u'state_times': {u'not_started': u'2013-04-30T20:37:25'},
                                       u'num_isos_finished': 0, u'iso_error_messages': {}}}
        renderer = status.ISOStatusRenderer(self.context)

        renderer.display_report(progress_report)

        # The sync reporting methods should be called
        self.assertEqual(_display_iso_sync_report.call_count, 1)
        self.assertEqual(type(_display_iso_sync_report.mock_calls[0][1][1]), progress.SyncProgressReport)
        self.assertEqual(_display_iso_sync_report.mock_calls[0][1][1].state,
                         progress.SyncProgressReport.STATE_NOT_STARTED)

        self.assertEqual(_display_manifest_sync_report.call_count, 1)
        self.assertEqual(type(_display_iso_sync_report.mock_calls[0][1][1]), progress.SyncProgressReport)
        self.assertEqual(_display_iso_sync_report.mock_calls[0][1][1].state,
                         progress.SyncProgressReport.STATE_NOT_STARTED)

        # The publish reporting should not be called
        self.assertEqual(_display_publish_report.call_count, 0)

    def test__display_iso_sync_report_during_complete_stage(self):
        """
        Test the ISOStatusRenderer._display_iso_sync_report method when the SyncProgressReport has entered the
        COMPLETE state (with three ISOs successfully downloaded). It should display completion
        progress to the user.
        """
        conduit = mock.MagicMock()
        finished_bytes = 1204
        total_bytes = 1204
        state_times = {progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS: datetime.utcnow()}
        sync_report = progress.SyncProgressReport(
            conduit, num_isos=3, num_isos_finished=3, total_bytes=total_bytes, finished_bytes=finished_bytes,
            state=progress.SyncProgressReport.STATE_COMPLETE, state_times=state_times)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's put the renderer in the manifest retrieval stage, simulating the SyncProgressReport having
        # just left that stage
        renderer._sync_state = progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        renderer.prompt.reset_mock()

        renderer._display_iso_sync_report(sync_report)

        renderer.prompt.write.assert_has_call('Downloading 3 ISOs.')
        # The _sync_state should have been updated to reflect the ISO downloading stage being complete
        self.assertEqual(renderer._sync_state, progress.SyncProgressReport.STATE_COMPLETE)
        # A progress bar should have been rendered
        self.assertEqual(renderer._sync_isos_bar.render.call_count, 1)
        args = renderer._sync_isos_bar.render.mock_calls[0][1]
        self.assertEqual(args[0], finished_bytes)
        self.assertEqual(args[1], total_bytes)

        # There should be one kwarg - message. It is non-deterministic, so let's just assert that it has some
        # of the right text in it
        kwargs = renderer._sync_isos_bar.render.mock_calls[0][2]
        self.assertEqual(len(kwargs), 1)
        self.assertTrue('ISOs: 3/3' in kwargs['message'])

        # A completion message should have been printed for the user
        self.assertEqual(renderer.prompt.render_success_message.mock_calls[0][2]['tag'], 'download_success')

    def test__display_iso_sync_report_during_isos_failed_state(self):
        """
        Test the ISOStatusRenderer._display_iso_sync_report method when the SyncProgressReport has entered
        STATE_ISOS_FAILED (with two ISOs successfully downloaded). It should display an error message
        to the user.
        """
        conduit = mock.MagicMock()
        finished_bytes = 1204
        total_bytes = 908
        iso_error_messages = {'bad.iso': 'Sorry, I will not tell you what happened.'}
        state_times = {progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS: datetime.utcnow()}
        sync_report = progress.SyncProgressReport(
            conduit, num_isos=3, num_isos_finished=2, total_bytes=total_bytes, finished_bytes=finished_bytes,
            state=progress.SyncProgressReport.STATE_ISOS_FAILED, state_times=state_times,
            iso_error_messages=iso_error_messages)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's put the renderer in the manifest retrieval stage, simulating the SyncProgressReport having
        # just left that stage
        renderer._sync_state = progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        renderer.prompt.reset_mock()

        renderer._display_iso_sync_report(sync_report)

        renderer.prompt.write.assert_has_call('Downloading 3 ISOs.')
        # The _sync_state should have been updated to reflect the ISO downloading stage having failed
        self.assertEqual(renderer._sync_state, progress.SyncProgressReport.STATE_ISOS_FAILED)
        # A progress bar should have been rendered
        self.assertEqual(renderer._sync_isos_bar.render.call_count, 1)
        args = renderer._sync_isos_bar.render.mock_calls[0][1]
        self.assertEqual(args[0], finished_bytes)
        self.assertEqual(args[1], total_bytes)

        # There should be one kwarg - message. It is non-deterministic, so let's just assert that it has some
        # of the right text in it
        kwargs = renderer._sync_isos_bar.render.mock_calls[0][2]
        self.assertEqual(len(kwargs), 1)
        self.assertTrue('ISOs: 2/3' in kwargs['message'])

        # A completion message should have been printed for the user
        self.assertEqual(renderer.prompt.render_failure_message.mock_calls[0][2]['tag'], 'download_failed')

        # The individual ISO that failed should have had its error message printed to screen
        self.assertTrue(iso_error_messages['bad.iso'] in
                        renderer.prompt.render_failure_message.mock_calls[1][1][0])
        self.assertEqual(renderer.prompt.render_failure_message.mock_calls[1][2]['tag'], 'iso_error_msg')

    def test__display_iso_sync_report_during_iso_stage_no_isos(self):
        """
        Test the ISOStatusRenderer._display_iso_sync_report method when the SyncProgressReport has entered the
        ISO retrieval stage (with no ISOs to download) from the manifest retrieval stage. It should just tell
        the user there is nothing to do.
        """
        conduit = mock.MagicMock()
        sync_report = progress.SyncProgressReport(
            conduit, num_isos=0, state=progress.SyncProgressReport.STATE_ISOS_IN_PROGRESS)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's put the renderer in the manifest retrieval stage, simulating the SyncProgressReport having
        # just left that stage
        renderer._sync_state = progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        renderer.prompt.reset_mock()

        renderer._display_iso_sync_report(sync_report)

        self.assertEqual(renderer.prompt.render_success_message.call_count, 1)
        self.assertTrue('no ISOs' in renderer.prompt.render_success_message.mock_calls[0][1][0])
        self.assertEqual(renderer.prompt.render_success_message.mock_calls[0][2]['tag'], 'none_to_download')
        # The _sync_state should have been updated to reflect the ISO downloading stage being complete
        self.assertEqual(renderer._sync_state, progress.SyncProgressReport.STATE_COMPLETE)

    def test__display_iso_sync_report_during_iso_stage_with_isos(self):
        """
        Test the ISOStatusRenderer._display_iso_sync_report method when the SyncProgressReport has entered the
        ISO retrieval stage (with three ISOs to download) from the manifest retrieval stage. It should display
        progress to the user.
        """
        conduit = mock.MagicMock()
        finished_bytes = 12
        total_bytes = 1204
        state_times = {progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS: datetime.utcnow()}
        sync_report = progress.SyncProgressReport(
            conduit, num_isos=3, total_bytes=total_bytes, finished_bytes=finished_bytes,
            state=progress.SyncProgressReport.STATE_ISOS_IN_PROGRESS, state_times=state_times)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's put the renderer in the manifest retrieval stage, simulating the SyncProgressReport having
        # just left that stage
        renderer._sync_state = progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        renderer.prompt.reset_mock()

        renderer._display_iso_sync_report(sync_report)

        renderer.prompt.write.assert_called_once_with('Downloading 3 ISOs.')
        # The _sync_state should have been updated to reflect the ISO downloading stage being in progress
        self.assertEqual(renderer._sync_state, progress.SyncProgressReport.STATE_ISOS_IN_PROGRESS)
        # A progress bar should have been rendered
        self.assertEqual(renderer._sync_isos_bar.render.call_count, 1)
        args = renderer._sync_isos_bar.render.mock_calls[0][1]
        self.assertEqual(args[0], finished_bytes)
        self.assertEqual(args[1], total_bytes)

        # There should be one kwarg - message. It is non-deterministic, so let's just assert that it has some
        # of the right text in it
        kwargs = renderer._sync_isos_bar.render.mock_calls[0][2]
        self.assertEqual(len(kwargs), 1)
        self.assertTrue('ISOs: 0/3' in kwargs['message'])

    def test__display_iso_sync_report_during_manifest_stage(self):
        """
        Test the ISOStatusRenderer._display_iso_sync_report method when the SyncProgressReport is in the
        manifest retrieval stage. It should not display anything to the user.
        """
        conduit = mock.MagicMock()
        sync_report = progress.SyncProgressReport(conduit,
            state=progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's also put the renderer in the manifest retrieval stage
        renderer._sync_state = progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS
        renderer.prompt.reset_mock()

        renderer._display_iso_sync_report(sync_report)

        # Because we are in the manifest state, this method should not do anything with the prompt
        self.assertEqual(renderer.prompt.mock_calls, [])

    def test__display_manifest_sync_report_manifest_complete(self):
        """
        Test behavior from _display_manifest_sync_report when the manifest is complete.
        """
        sync_report = progress.SyncProgressReport(None,
            state=progress.SyncProgressReport.STATE_ISOS_IN_PROGRESS)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's also put the renderer in the manifest retrieval stage
        renderer._sync_state = progress.SyncProgressReport.STATE_NOT_STARTED
        renderer.prompt.reset_mock()

        renderer._display_manifest_sync_report(sync_report)

        # There should be one message printed to the user that tells them the manifest is complete
        self.assertEqual(len(renderer.prompt.mock_calls), 1)
        self.assertEqual(renderer.prompt.mock_calls[0][2]['tag'], 'manifest_downloaded')
        # The renderer state should have been advanced to STATE_MANIFEST_IN_PROGRESS, but not beyond, as
        # _display_iso_sync_report will move it into the next state
        self.assertEqual(renderer._sync_state, progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS)

    def test__display_manifest_sync_report_manifest_failed(self):
        """
        Test behavior from _display_manifest_sync_report when the manifest failed to be retrieved.
        """
        conduit = mock.MagicMock()
        error_message = 'It broke.'
        sync_report = progress.SyncProgressReport(conduit, error_message=error_message,
            state=progress.SyncProgressReport.STATE_MANIFEST_FAILED)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's also put the renderer in the manifest retrieval stage
        renderer._sync_state = progress.SyncProgressReport.STATE_NOT_STARTED
        renderer.prompt.reset_mock()

        renderer._display_manifest_sync_report(sync_report)

        # There should be two calls to mock. One to report the manifest failure, and one to report the reason.
        self.assertEqual(len(renderer.prompt.mock_calls), 2)
        self.assertEqual(renderer.prompt.mock_calls[0][2]['tag'], 'manifest_failed')

        # Make sure we told the user the error message
        self.assertEqual(renderer.prompt.mock_calls[1][2]['tag'], 'manifest_error_message')
        # The specific error message passed from the sync_report should have been printed
        self.assertTrue(error_message in renderer.prompt.mock_calls[1][1][0])

    def test__display_manifest_sync_report_manifest_in_progress(self):
        """
        Test behavior from _display_manifest_sync_report when the manifest is currently in progress.
        """
        sync_report = progress.SyncProgressReport(None,
            state=progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's also put the renderer in the manifest retrieval stage
        renderer._sync_state = progress.SyncProgressReport.STATE_NOT_STARTED
        renderer.prompt.reset_mock()

        renderer._display_manifest_sync_report(sync_report)

        # There should be one message printed to the user that tells them the manifest is being downloaded
        self.assertEqual(len(renderer.prompt.mock_calls), 1)
        self.assertEqual(renderer.prompt.mock_calls[0][2]['tag'], 'downloading_manifest')
        # The renderer state should have been advanced to STATE_MANIFEST_IN_PROGRESS
        self.assertEqual(renderer._sync_state, progress.SyncProgressReport.STATE_MANIFEST_IN_PROGRESS)

    def test__display_manifest_sync_report_not_started(self):
        """
        Before the download starts, the _display_manifest_sync_report() method should not do anything.
        """
        conduit = mock.MagicMock()
        sync_report = progress.SyncProgressReport(conduit,
            state=progress.SyncProgressReport.STATE_NOT_STARTED)
        renderer = status.ISOStatusRenderer(self.context)
        # Let's also put the renderer in the manifest retrieval stage
        renderer._sync_state = progress.SyncProgressReport.STATE_NOT_STARTED
        renderer.prompt.reset_mock()

        renderer._display_manifest_sync_report(sync_report)

        self.assertEqual(len(renderer.prompt.mock_calls), 0)

    def test__display_publish_report_failed(self):
        """
        In the event of failure, the _display_publish_report() method print the message to the user.
        """
        conduit = mock.MagicMock()
        error_message = 'You fail.'
        sync_report = progress.PublishProgressReport(conduit, error_message=error_message,
            state=progress.PublishProgressReport.STATE_FAILED)
        renderer = status.ISOStatusRenderer(self.context)
        renderer.prompt.reset_mock()

        renderer._display_publish_report(sync_report)

        # There should be two prints, one to tell the user it failed, and another to tell the user the message
        self.assertEqual(len(renderer.prompt.mock_calls), 2)
        self.assertEqual(renderer.prompt.render_failure_message.mock_calls[0][2]['tag'], 'publish_failed')
        self.assertTrue(error_message in renderer.prompt.write.mock_calls[0][1][0])

    def test__display_publish_report_not_started(self):
        """
        Before the download starts, the _display_publish_report() method should not do anything.
        """
        conduit = mock.MagicMock()
        sync_report = progress.PublishProgressReport(conduit,
            state=progress.PublishProgressReport.STATE_NOT_STARTED)
        renderer = status.ISOStatusRenderer(self.context)
        renderer.prompt.reset_mock()

        renderer._display_publish_report(sync_report)

        # Nothing should be printed
        self.assertEqual(len(renderer.prompt.mock_calls), 0)

    def test__display_publish_report_success(self):
        """
        The _display_publish_report() method should print a success message to the user.
        """
        conduit = mock.MagicMock()
        sync_report = progress.PublishProgressReport(conduit,
            state=progress.PublishProgressReport.STATE_COMPLETE)
        renderer = status.ISOStatusRenderer(self.context)
        renderer.prompt.reset_mock()

        renderer._display_publish_report(sync_report)

        # There should be two prints, one to tell the user it failed, and another to tell the user the message
        self.assertEqual(len(renderer.prompt.mock_calls), 1)
        self.assertEqual(renderer.prompt.render_success_message.mock_calls[0][2]['tag'], 'publish_success')


class TestHumanReadableBytes(unittest.TestCase):
    """
    Test the status.human_readable_bytes() method.
    """
    def test_bytes(self):
        """
        Test correct behavior when bytes are passed in.
        """
        self.assertEqual(status.human_readable_bytes(42), '42 B')

    def test_kilobytes(self):
        """
        Test correct behavior when kB are passed.
        """
        self.assertEqual(status.human_readable_bytes(4096), '4.0 kB')

    def test_megabytes(self):
        """
        Test correct behavior when MB are passed.
        """
        self.assertEqual(status.human_readable_bytes(97464344), '92.9 MB')

    def test_gigabytes(self):
        """
        Test correct behavior when GB are passed.
        """
        self.assertEqual(status.human_readable_bytes(17584619520), '16.4 GB')

    def test_terrabytes(self):
        """
        Test correct behavior when TB are passed.
        """
        self.assertEqual(status.human_readable_bytes(40444624896000), '36.8 TB')
