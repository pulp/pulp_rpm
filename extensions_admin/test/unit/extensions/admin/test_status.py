# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import mock

from pulp.client.extensions.core import PulpPrompt
from pulp_rpm.common import constants, ids
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extensions.admin import status


class TestRpmExportStatusRenderer(PulpClientTests):
    """
    A set of tests for the rpm export distributor status renderer
    """
    def setUp(self):
        super(TestRpmExportStatusRenderer, self).setUp()

        self.renderer = status.RpmExportStatusRenderer(self.context)
        # A sample progress report dictionary
        self.progress = {
            ids.TYPE_ID_DISTRIBUTOR_EXPORT: {
                ids.TYPE_ID_ERRATA: {
                    constants.PROGRESS_NUM_SUCCESS_KEY: 0,
                    constants.PROGRESS_NUM_ERROR_KEY: 0,
                    constants.PROGRESS_ITEMS_LEFT_KEY: 10,
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                    constants.PROGRESS_ITEMS_TOTAL_KEY: 10,
                    constants.PROGRESS_ERROR_DETAILS_KEY: []
                },
                constants.PROGRESS_PUBLISH_HTTP: {
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED
                },
                constants.PROGRESS_PUBLISH_HTTPS: {
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED
                },
                constants.PROGRESS_ISOS_KEYWORD: {
                    constants.PROGRESS_NUM_SUCCESS_KEY: 0,
                    constants.PROGRESS_NUM_ERROR_KEY: 0,
                    constants.PROGRESS_ITEMS_LEFT_KEY: 1,
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                    constants.PROGRESS_ITEMS_TOTAL_KEY: 1,
                    constants.PROGRESS_ERROR_DETAILS_KEY: []
                },
                ids.TYPE_ID_DISTRO: {
                    constants.PROGRESS_NUM_SUCCESS_KEY: 0,
                    constants.PROGRESS_NUM_ERROR_KEY: 0,
                    constants.PROGRESS_ITEMS_LEFT_KEY: 1,
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                    constants.PROGRESS_ITEMS_TOTAL_KEY: 1,
                    constants.PROGRESS_ERROR_DETAILS_KEY: []
                },
                ids.TYPE_ID_RPM: {
                    constants.PROGRESS_NUM_SUCCESS_KEY: 0,
                    constants.PROGRESS_NUM_ERROR_KEY: 0,
                    constants.PROGRESS_ITEMS_LEFT_KEY: 43,
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                    constants.PROGRESS_ITEMS_TOTAL_KEY: 43,
                    constants.PROGRESS_ERROR_DETAILS_KEY: []
                },
                constants.PROGRESS_METADATA_KEYWORD: {
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED
                }
            }
        }

        status.render_general_spinner_step = mock.Mock(wraps=status.render_general_spinner_step)
        status.render_itemized_in_progress_state = mock.Mock(wraps=status.render_itemized_in_progress_state)

    def test_display_report(self):
        # Setup
        self.renderer.render_rpms_step = mock.Mock()
        self.renderer.render_errata_step = mock.Mock()
        self.renderer.render_distribution_publish_step = mock.Mock()
        self.renderer.render_generate_metadata_step = mock.Mock()
        self.renderer.render_isos_step = mock.Mock()
        self.renderer.render_publish_http_step = mock.Mock()
        self.renderer.render_publish_https_step = mock.Mock()

        # Test
        self.renderer.display_report(self.progress)
        self.renderer.render_rpms_step.assert_called_once_with(self.progress)
        self.renderer.render_errata_step.assert_called_once_with(self.progress)
        self.renderer.render_distribution_publish_step.assert_called_once_with(self.progress)
        self.renderer.render_generate_metadata_step.assert_called_once_with(self.progress)
        self.renderer.render_isos_step.assert_called_once_with(self.progress)
        self.renderer.render_publish_http_step.assert_called_once_with(self.progress)
        self.renderer.render_publish_https_step.assert_called_once_with(self.progress)

    def test_render_rpms_step(self):
        # Setup
        data = self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_RPM]
        self.renderer.prompt.write = mock.Mock(spec=PulpPrompt)

        # Test that when the section has a state that isn't in progress, nothing is done
        self.renderer.render_rpms_step(self.progress)
        self.assertEqual(0, status.render_itemized_in_progress_state.call_count)

        # Change the state to running and call render_rpms_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_RPM] = data
        self.renderer.render_rpms_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(data, status.render_itemized_in_progress_state.call_args[0][1])
        self.assertEqual(constants.STATE_RUNNING,
                         status.render_itemized_in_progress_state.call_args[0][4])
        self.assertEqual(constants.STATE_RUNNING, self.renderer.rpms_last_state)

        # Change the state to failed and call render_rpms_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_RPM] = data
        self.renderer.render_rpms_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(constants.STATE_FAILED, self.renderer.rpms_last_state)

    def test_render_errata_step(self):
        # Setup
        data = self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_ERRATA]
        self.renderer.prompt.write = mock.Mock(spec=PulpPrompt)

        # Test that when the section has a state that isn't in progress, nothing is done
        self.renderer.render_errata_step(self.progress)
        self.assertEqual(0, status.render_itemized_in_progress_state.call_count)

        # Change the state to running and call render_errata_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_ERRATA] = data
        self.renderer.render_errata_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(data, status.render_itemized_in_progress_state.call_args[0][1])
        self.assertEqual(constants.STATE_RUNNING,
                         status.render_itemized_in_progress_state.call_args[0][4])
        self.assertEqual(constants.STATE_RUNNING, self.renderer.errata_last_state)

        # Change the state to failed and call render_errata_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_ERRATA] = data
        self.renderer.render_errata_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(constants.STATE_FAILED, self.renderer.errata_last_state)

    def test_render_distribution_step(self):
        # Setup
        data = self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_DISTRO]
        self.renderer.prompt.write = mock.Mock(spec=PulpPrompt)

        # Test that when the section has a state that isn't in progress, nothing is done
        self.renderer.render_distribution_publish_step(self.progress)
        self.assertEqual(0, status.render_itemized_in_progress_state.call_count)

        # Change the state to running and call render_distribution_publish_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_DISTRO] = data
        self.renderer.render_distribution_publish_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(data, status.render_itemized_in_progress_state.call_args[0][1])
        self.assertEqual(constants.STATE_RUNNING,
                         status.render_itemized_in_progress_state.call_args[0][4])
        self.assertEqual(constants.STATE_RUNNING, self.renderer.distributions_last_state)

        # Change the state to failed and call render_distribution_publish_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][ids.TYPE_ID_DISTRO] = data
        self.renderer.render_distribution_publish_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(constants.STATE_FAILED, self.renderer.distributions_last_state)

    def test_render_isos_step(self):
        # Setup
        data = self.progress[ids.EXPORT_DISTRIBUTOR_ID][constants.PROGRESS_ISOS_KEYWORD]
        self.renderer.prompt.write = mock.Mock(spec=PulpPrompt)

        # Test that when the section has a state that isn't in progress, nothing is done
        self.renderer.render_isos_step(self.progress)
        self.assertEqual(0, status.render_itemized_in_progress_state.call_count)

        # Change the state to running and call render_isos_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][constants.PROGRESS_ISOS_KEYWORD] = data
        self.renderer.render_isos_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(data, status.render_itemized_in_progress_state.call_args[0][1])
        self.assertEqual(constants.STATE_RUNNING,
                         status.render_itemized_in_progress_state.call_args[0][4])
        self.assertEqual(constants.STATE_RUNNING, self.renderer.isos_last_state)

        # Change the state to failed and call render_isos_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        self.progress[ids.EXPORT_DISTRIBUTOR_ID][constants.PROGRESS_ISOS_KEYWORD] = data
        self.renderer.render_isos_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(constants.STATE_FAILED, self.renderer.isos_last_state)

    def test_render_generate_metadata_step(self):
        """
        This just checks that the render_general_spinner_step gets called for
        render_generate_metadata_step and is handed the correct spinner
        """
        self.renderer.render_generate_metadata_step(self.progress)
        self.assertEqual(self.renderer.generate_metadata_spinner,
                         status.render_general_spinner_step.call_args[0][1])
        self.assertEqual(constants.STATE_NOT_STARTED,
                         status.render_general_spinner_step.call_args[0][2])

        # Update the state and assert that the last_state is updated correctly
        self.progress[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_METADATA_KEYWORD] = {
            constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING
        }
        self.renderer.render_generate_metadata_step(self.progress)
        self.assertEqual(constants.STATE_RUNNING, self.renderer.generate_metadata_last_state)

    def test_render_publish_http_step(self):
        """
        This just checks that the render_general_spinner_step gets called for render_publish_http_step
        and is handed the correct spinner
        """
        self.renderer.render_publish_http_step(self.progress)
        self.assertEqual(self.renderer.publish_http_spinner,
                         status.render_general_spinner_step.call_args[0][1])
        self.assertEqual(constants.STATE_NOT_STARTED,
                         status.render_general_spinner_step.call_args[0][2])

        # Update the state and assert that the last_state is updated correctly
        self.progress[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_PUBLISH_HTTP] = {
            constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING
        }
        self.renderer.render_publish_http_step(self.progress)
        self.assertEqual(constants.STATE_RUNNING, self.renderer.publish_http_last_state)

    def test_render_publish_https_step(self):
        """
        This just checks that the render_general_spinner_step gets called for render_publish_https_step
        and is handed the correct spinner
        """
        self.renderer.render_publish_https_step(self.progress)
        self.assertEqual(self.renderer.publish_https_spinner,
                         status.render_general_spinner_step.call_args[0][1])
        self.assertEqual(constants.STATE_NOT_STARTED,
                         status.render_general_spinner_step.call_args[0][2])

        # Update the state and assert that the last_state is updated correctly
        self.progress[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_PUBLISH_HTTPS] = {
            constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING
        }
        self.renderer.render_publish_https_step(self.progress)
        self.assertEqual(constants.STATE_RUNNING, self.renderer.publish_https_last_state)


class TestGroupExportStatusRenderer(PulpClientTests):
    def setUp(self):
        super(TestGroupExportStatusRenderer, self).setUp()

        self.renderer = status.RpmGroupExportStatusRenderer(self.context)
        self.progress = {
            ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT: {
                constants.PROGRESS_PUBLISH_HTTP: {
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                },
                constants.PROGRESS_ISOS_KEYWORD: {
                    constants.PROGRESS_NUM_SUCCESS_KEY: 0,
                    constants.PROGRESS_NUM_ERROR_KEY: 0,
                    constants.PROGRESS_ITEMS_LEFT_KEY: 2,
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                    constants.PROGRESS_ITEMS_TOTAL_KEY: 2,
                    constants.PROGRESS_ERROR_DETAILS_KEY: []
                },
                constants.PROGRESS_REPOS_KEYWORD: {
                    constants.PROGRESS_NUM_SUCCESS_KEY: 0,
                    constants.PROGRESS_NUM_ERROR_KEY: 0,
                    constants.PROGRESS_ITEMS_LEFT_KEY: 5,
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                    constants.PROGRESS_ITEMS_TOTAL_KEY: 5,
                    constants.PROGRESS_ERROR_DETAILS_KEY: []
                },
                constants.PROGRESS_PUBLISH_HTTPS: {
                    constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED,
                }
            }
        }

        status.render_general_spinner_step = mock.Mock(wraps=status.render_general_spinner_step)
        status.render_itemized_in_progress_state = mock.Mock(wraps=status.render_itemized_in_progress_state)

    def test_display_report(self):
        # Setup
        self.renderer.render_repos_step = mock.Mock(status.RpmGroupExportStatusRenderer.render_repos_step)
        self.renderer.render_isos_step = mock.Mock(status.RpmGroupExportStatusRenderer.render_isos_step)
        self.renderer.render_publish_http_step = mock.Mock(status.RpmGroupExportStatusRenderer.render_publish_http_step)
        self.renderer.render_publish_https_step = mock.Mock(status.RpmGroupExportStatusRenderer.render_publish_https_step)

        # Test
        self.renderer.display_report(self.progress)
        self.renderer.render_repos_step.assert_called_once_with(self.progress)
        self.renderer.render_isos_step.assert_called_once_with(self.progress)
        self.renderer.render_publish_http_step.assert_called_once_with(self.progress)
        self.renderer.render_publish_https_step.assert_called_once_with(self.progress)

    def test_render_repos_step(self):
        # Setup
        data = self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_REPOS_KEYWORD]
        self.renderer.prompt.write = mock.Mock(spec=PulpPrompt)

        # Test that when the section has a state that isn't in progress, nothing is done
        self.renderer.render_repos_step(self.progress)
        self.assertEqual(0, status.render_itemized_in_progress_state.call_count)

        # Change the state to running and call render_repos_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_REPOS_KEYWORD] = data
        self.renderer.render_repos_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(data, status.render_itemized_in_progress_state.call_args[0][1])
        self.assertEqual(constants.STATE_RUNNING,
                         status.render_itemized_in_progress_state.call_args[0][4])
        self.assertEqual(constants.STATE_RUNNING, self.renderer.repos_last_state)

        # Change the state to failed and call render_repos_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_REPOS_KEYWORD] = data
        self.renderer.render_repos_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(constants.STATE_FAILED, self.renderer.repos_last_state)

    def test_render_isos_step(self):
        # Setup
        data = self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_ISOS_KEYWORD]
        self.renderer.prompt.write = mock.Mock(spec=PulpPrompt)

        # Test that when the section has a state that isn't in progress, nothing is done
        self.renderer.render_isos_step(self.progress)
        self.assertEqual(0, status.render_itemized_in_progress_state.call_count)

        # Change the state to running and call render_isos_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
        self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_ISOS_KEYWORD] = data
        self.renderer.render_isos_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(data, status.render_itemized_in_progress_state.call_args[0][1])
        self.assertEqual(constants.STATE_RUNNING,
                         status.render_itemized_in_progress_state.call_args[0][4])
        self.assertEqual(constants.STATE_RUNNING, self.renderer.isos_last_state)

        # Change the state to failed and call render_isos_step again
        data[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_REPOS_KEYWORD] = data
        self.renderer.render_isos_step(self.progress)
        self.assertEqual(1, status.render_itemized_in_progress_state.call_count)
        self.assertEqual(constants.STATE_FAILED, self.renderer.isos_last_state)

    def test_render_publish_http_step(self):
        """
        This just checks that the render_general_spinner_step gets called for render_publish_http_step
        and is handed the correct spinner
        """
        self.renderer.render_publish_http_step(self.progress)
        self.assertEqual(self.renderer.publish_http_spinner,
                         status.render_general_spinner_step.call_args[0][1])
        self.assertEqual(constants.STATE_NOT_STARTED,
                         status.render_general_spinner_step.call_args[0][2])

        # Update the state and assert that the last_state is updated correctly
        self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_PUBLISH_HTTP] = {
            constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING
        }
        self.renderer.render_publish_http_step(self.progress)
        self.assertEqual(constants.STATE_RUNNING, self.renderer.publish_http_last_state)

    def test_render_publish_https_step(self):
        """
        This just checks that the render_general_spinner_step gets called for render_publish_https_step
        and is handed the correct spinner
        """
        self.renderer.render_publish_https_step(self.progress)
        self.assertEqual(self.renderer.publish_https_spinner,
                         status.render_general_spinner_step.call_args[0][1])
        self.assertEqual(constants.STATE_NOT_STARTED,
                         status.render_general_spinner_step.call_args[0][2])

        # Update the state and assert that the last_state is updated correctly
        self.progress[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_PUBLISH_HTTPS] = {
            constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING
        }
        self.renderer.render_publish_https_step(self.progress)
        self.assertEqual(constants.STATE_RUNNING, self.renderer.publish_https_last_state)
