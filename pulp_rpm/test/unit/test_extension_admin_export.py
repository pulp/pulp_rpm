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
from pulp.bindings.exceptions import NotFoundException
from pulp.bindings.responses import Response
from pulp.client.commands import options
from pulp.common import tags as tag_utils

from pulp_rpm.common import constants, ids
from pulp_rpm.extension.admin import export, status
import rpm_support_base


class TestRepoExportRunCommand(rpm_support_base.PulpClientTests):
    """
    Tests the rpm repo export run command. This makes use of the platform RunPublishRepositoryCommand,
    so all that's tested here is that the constructor is called correctly.
    """

    @mock.patch('pulp.client.commands.repo.sync_publish.RunPublishRepositoryCommand.__init__',
                autospec=True)
    def test_rpm_export___init__(self, mock_superclass_init, ):
        """
        Test that the __init__ function calls super's __init__ function with the correct
        override arguments
        """
        # Setup
        expected_options = [export.OPTION_EXPORT_DIR, export.OPTION_END_DATE, export.OPTION_START_DATE,
                            export.OPTION_ISO_PREFIX, export.OPTION_ISO_SIZE]

        # Test
        export.RpmExportCommand(self.context)
        actual_kwargs = mock_superclass_init.call_args_list[0][1]
        self.assertEqual(actual_kwargs['context'], self.context)
        self.assertEqual(actual_kwargs['description'], export.DESC_EXPORT_RUN)
        self.assertEqual(actual_kwargs['distributor_id'], ids.TYPE_ID_DISTRIBUTOR_EXPORT)
        self.assertEqual(set(actual_kwargs['override_config_options']), set(expected_options))
        self.assertTrue(isinstance(actual_kwargs['renderer'], status.RpmExportStatusRenderer))


class TestRepoGroupExportRunCommand(rpm_support_base.PulpClientTests):
    """
    This tests the rpm repo group export run command.
    """
    def setUp(self):
        super(TestRepoGroupExportRunCommand, self).setUp()
        export._get_publish_task_id = mock.MagicMock(spec=export._get_publish_task_id)
        self.kwargs = {
            options.OPTION_GROUP_ID.keyword: 'test-group',
            export.OPTION_ISO_PREFIX.keyword: None,
            export.OPTION_ISO_SIZE.keyword: None,
            export.OPTION_START_DATE.keyword: None,
            export.OPTION_END_DATE.keyword: None,
            export.OPTION_EXPORT_DIR.keyword: None,
            export.SERVE_HTTP: True,
            export.SERVE_HTTPS: True,
            export.BACKGROUND: True
        }

    @mock.patch('pulp.client.extensions.extensions.PulpCliCommand.create_flag', autospec=True)
    @mock.patch('okaara.cli.Command.add_option', autospec=True)
    def test_rpm_group_export_setup(self, mock_add_option, mock_create_flag):
        """
        Test to make sure the export run command is set up correctly
        """
        mock_renderer = mock.Mock(spec=status.RpmGroupExportStatusRenderer)
        expected_options = [options.OPTION_GROUP_ID, export.OPTION_EXPORT_DIR, export.OPTION_END_DATE,
                            export.OPTION_START_DATE, export.OPTION_ISO_PREFIX, export.OPTION_ISO_SIZE]

        # Test
        export.RpmGroupExportCommand(self.context, mock_renderer, ids.EXPORT_GROUP_DISTRIBUTOR_ID)

        # Check that all the flags were added
        self.assertEqual(3, mock_create_flag.call_count)
        self.assertEqual('--' + export.SERVE_HTTP, mock_create_flag.call_args_list[0][0][1])
        self.assertEqual(export.DESC_SERVE_HTTP, mock_create_flag.call_args_list[0][0][2])
        self.assertEqual('--' + export.SERVE_HTTPS, mock_create_flag.call_args_list[1][0][1])
        self.assertEqual(export.DESC_SERVE_HTTPS, mock_create_flag.call_args_list[1][0][2])
        self.assertEqual('--' + export.BACKGROUND, mock_create_flag.call_args_list[2][0][1])
        self.assertEqual(export.DESC_BACKGROUND, mock_create_flag.call_args_list[2][0][2])

        # Check that all the options were added
        actual_options = []
        for call_args, kwargs in mock_add_option.call_args_list:
            actual_options.append(call_args[1])
        self.assertEqual(set(actual_options), set(expected_options))

    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.create', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributor', autospec=True)
    def test_rpm_group_export_missing_distributor(self, mock_distributor, mock_create):
        """
        Test that when there is no distributor attached to the repository group, one is added
        """
        # Setup
        mock_distributor.side_effect = NotFoundException(mock.Mock())

        expected_distributor_config = {
            constants.PUBLISH_HTTP_KEYWORD: True,
            constants.PUBLISH_HTTPS_KEYWORD: True,
        }

        # Test
        command = export.RpmGroupExportCommand(self.context, mock.MagicMock(),
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)

        # Assert that the call get get the distributor was made correctly
        self.assertEqual(1, mock_distributor.call_count)
        self.assertEqual('test-group', mock_distributor.call_args[0][1])
        self.assertEqual(ids.EXPORT_GROUP_DISTRIBUTOR_ID, mock_distributor.call_args[0][2])

        # Assert that when the NonFoundException is raised, a call to create a distributor is made
        self.assertEqual(1, mock_create.call_count)
        self.assertEqual('test-group', mock_create.call_args[0][1])
        self.assertEqual(ids.EXPORT_GROUP_DISTRIBUTOR_ID, mock_create.call_args[0][2])
        self.assertEqual(expected_distributor_config, mock_create.call_args[0][3])
        self.assertEqual(ids.EXPORT_GROUP_DISTRIBUTOR_ID, mock_create.call_args[0][4])

    @mock.patch('pulp.bindings.repo_groups.RepoGroupActionAPI.publish', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributor', autospec=True)
    def test_rpm_group_export_existing_task(self, mock_distributor, mock_publish):
        """
        Make sure that when there is already a publish operation in progress for the repository, a second
        one is not started
        """
        # Setup
        mock_distributor.return_value = (200, mock.Mock(spec=Response))
        export._get_publish_task_id.return_value = 'Not None'

        # Test
        command = export.RpmGroupExportCommand(self.context, mock.MagicMock(),
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)
        self.assertEqual(0, mock_publish.call_count)

    @mock.patch('pulp.client.commands.repo.status.status.display_task_status', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributor', autospec=True)
    def test_rpm_group_export_background(self, mock_distributor, mock_display_task_status):
        """
        Test that when the background flag is True display_task_status is not called
        """
        # Setup
        mock_distributor.return_value = (200, mock.Mock(spec=Response))

        # Test that when background is True, display_task_status is not called
        command = export.RpmGroupExportCommand(self.context, mock.MagicMock(),
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)
        self.assertEqual(0, mock_display_task_status.call_count)

    @mock.patch('pulp.client.commands.repo.status.status.display_task_status', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupActionAPI.publish', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributor', autospec=True)
    def test_rpm_group_export_run(self, mock_distributor, mock_publish, mock_display_task_status):
        """
        Test to make sure the publish binding is called correctly and that display_task_status is then
        called.
        """
        # Setup
        response = Response(200, mock.Mock())
        response.response_body.task_id = 'fake-id'
        mock_publish.return_value = response
        mock_distributor.return_value = (200, mock.Mock(spec=Response))
        export._get_publish_task_id.return_value = None
        self.kwargs[export.BACKGROUND] = False
        mock_renderer = mock.MagicMock()
        expected_publish_config = {
            constants.PUBLISH_HTTP_KEYWORD: True,
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.ISO_PREFIX_KEYWORD: None,
            constants.ISO_SIZE_KEYWORD: None,
            constants.START_DATE_KEYWORD: None,
            constants.END_DATE_KEYWORD: None,
            constants.EXPORT_DIRECTORY_KEYWORD: None,
        }

        # Test
        command = export.RpmGroupExportCommand(self.context, mock_renderer,
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)

        # Assert that publish was called with the correct arguments
        self.assertEqual(1, mock_publish.call_count)
        self.assertEqual('test-group', mock_publish.call_args[0][1])
        self.assertEqual(ids.EXPORT_GROUP_DISTRIBUTOR_ID, mock_publish.call_args[0][2])
        self.assertEqual(expected_publish_config, mock_publish.call_args[0][3])

        # Assert that display_task_status was called with the correct arguments
        mock_display_task_status.assert_called_once_with(self.context, mock_renderer, 'fake-id')


class TestRepoGroupExportStatusCommand(rpm_support_base.PulpClientTests):
    """
    Tests for the GroupExportStatusCommand class
    """
    @mock.patch('okaara.cli.Command.add_option', autospec=True)
    def test_repo_group_export_status_structure(self, mock_add_option):
        """
        Test to make sure the correct options are added
        """
        # Setup
        mock_renderer = mock.Mock(spec=status.RpmGroupExportStatusRenderer)

        # Test
        command = export.GroupExportStatusCommand(self.context, mock_renderer)
        self.assertEqual(1, mock_add_option.call_count)
        self.assertEqual(options.OPTION_GROUP_ID, mock_add_option.call_args[0][1])
        self.assertEqual('status', command.name)
        self.assertEqual(export.DESC_GROUP_EXPORT_STATUS, command.description)
        self.assertEqual(command.run, command.method)

    @mock.patch('pulp.client.commands.repo.status.status.display_task_status', autospec=True)
    def test_repo_group_export_status_run(self, mock_task_status):
        """
        Test the case of an existing task that should be tracked
        """
        # Setup
        export._get_publish_task_id = mock.Mock(spec=export._get_publish_task_id, return_value='task_id')
        mock_renderer = mock.Mock()

        # Test
        command = export.GroupExportStatusCommand(self.context, mock_renderer)
        command.run(**{options.OPTION_GROUP_ID.keyword: 'test-group'})

        export._get_publish_task_id.assert_called_once_with('repository_group', 'test-group',
                                                            self.context)
        mock_task_status.assert_called_once_with(self.context, mock_renderer, 'task_id')

    @mock.patch('pulp.client.commands.repo.status.status.display_task_status', autospec=True)
    def test_repo_group_export_status_no_task(self, mock_task_status):
        """
        Test that when no task id is found, display_task_status is not called
        """
        # Setup
        export._get_publish_task_id = mock.Mock(spec=export._get_publish_task_id, return_value=None)
        mock_renderer = mock.Mock()

        # Test
        command = export.GroupExportStatusCommand(self.context, mock_renderer)
        command.run(**{options.OPTION_GROUP_ID.keyword: 'test-group'})
        self.assertEqual(0, mock_task_status.call_count)


class TestGetPublishTaskId(rpm_support_base.PulpClientTests):
    """
    Tests for the _get_publish_task_id helper method
    """
    @mock.patch('pulp.bindings.tasks.TasksAPI.get_all_tasks', autospec=True)
    @mock.patch('pulp.client.commands.repo.status.tasks.relevant_existing_task_id', autospec=True)
    def test_get_publish_task_id(self, mock_existing_task_id, mock_get_all_tasks):
        # Setup
        mock_get_all_tasks.return_value = Response(200, [])
        mock_existing_task_id.return_value = 'fake result'
        expected_tags = [tag_utils.resource_tag('fake-type', 'fake-id'),
                         tag_utils.action_tag(tag_utils.ACTION_PUBLISH_TYPE)]

        # Test
        result = export._get_publish_task_id('fake-type', 'fake-id', self.context)
        self.assertEqual(1, mock_get_all_tasks.call_count)
        self.assertEqual(expected_tags, mock_get_all_tasks.call_args[0][1])
        mock_existing_task_id.assert_called_once_with([])
        self.assertEqual(result, 'fake result')
