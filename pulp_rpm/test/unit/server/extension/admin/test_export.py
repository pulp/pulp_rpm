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

import unittest

import mock

from pulp.bindings.exceptions import NotFoundException
from pulp.bindings.responses import Response, Task, COMPLETED_STATES
from pulp.client.commands import options
from pulp.client.commands.polling import FLAG_BACKGROUND
from pulp.common import tags as tag_utils
from pulp.devel.unit.util import compare_dict

from pulp_rpm.common import constants, ids
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extension.admin import export, status
from pulp_rpm.devel import rpm_support_base


class TestRepoExportRunCommand(PulpClientTests):
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


class TestRepoGroupExportRunCommand(PulpClientTests):
    """
    This tests the rpm repo group export run command.
    """
    def setUp(self):
        super(TestRepoGroupExportRunCommand, self).setUp()
        self.patcher = mock.patch('pulp_rpm.extension.admin.export._get_publish_tasks',
                                  spec=export._get_publish_tasks)
        self.mock_get_publish_tasks = self.patcher.start()
        self.mock_get_publish_tasks.return_value = []

        self.kwargs = {
            options.OPTION_GROUP_ID.keyword: 'test-group',
            export.OPTION_ISO_PREFIX.keyword: None,
            export.OPTION_ISO_SIZE.keyword: None,
            export.OPTION_START_DATE.keyword: None,
            export.OPTION_END_DATE.keyword: None,
            export.OPTION_EXPORT_DIR.keyword: None,
            export.SERVE_HTTP: True,
            export.SERVE_HTTPS: True
        }

    def tearDown(self):
        self.patcher.stop()

    @mock.patch('pulp.client.extensions.extensions.PulpCliCommand.create_flag', autospec=True)
    @mock.patch('okaara.cli.Command.add_option', autospec=True)
    def test_rpm_group_export_setup(self, mock_add_option, mock_create_flag):
        """
        Test to make sure the export run command is set up correctly
        """
        mock_renderer = mock.Mock(spec=status.RpmGroupExportStatusRenderer)
        expected_options = [FLAG_BACKGROUND,
                            options.OPTION_GROUP_ID,
                            export.OPTION_EXPORT_DIR,
                            export.OPTION_END_DATE,
                            export.OPTION_START_DATE,
                            export.OPTION_ISO_PREFIX,
                            export.OPTION_ISO_SIZE]

        # Test
        export.RpmGroupExportCommand(self.context, mock_renderer, ids.EXPORT_GROUP_DISTRIBUTOR_ID)

        # Check that all the flags were added
        self.assertEqual(2, mock_create_flag.call_count)
        self.assertEqual('--' + export.SERVE_HTTP, mock_create_flag.call_args_list[0][0][1])
        self.assertEqual(export.DESC_SERVE_HTTP, mock_create_flag.call_args_list[0][0][2])
        self.assertEqual('--' + export.SERVE_HTTPS, mock_create_flag.call_args_list[1][0][1])
        self.assertEqual(export.DESC_SERVE_HTTPS, mock_create_flag.call_args_list[1][0][2])

        # Check that all the options were added
        actual_options = []
        for call_args, kwargs in mock_add_option.call_args_list:
            actual_options.append(call_args[1])

        self.assertEqual(set(actual_options), set(expected_options))

    @mock.patch('pulp.bindings.repo_groups.RepoGroupActionAPI.publish', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.create', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributors', autospec=True)
    def test_rpm_group_export_missing_distributor(self, mock_distributors, mock_create,
                                                  mock_publish):
        """
        Test that when there is no distributor attached to the repository group, one is added
        """
        # Setup
        mock_distributors.return_value = Response(200, [])
        mock_publish.return_value = Response(200, [])

        expected_distributor_config = {
            constants.PUBLISH_HTTP_KEYWORD: True,
            constants.PUBLISH_HTTPS_KEYWORD: True,
        }

        # Test
        command = export.RpmGroupExportCommand(self.context, mock.MagicMock(),
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)

        # Assert that the call get get the distributor was made correctly
        self.assertEqual(1, mock_distributors.call_count)
        self.assertEqual('test-group', mock_distributors.call_args[0][1])

        # Assert that when the NonFoundException is raised, a call to create a distributor is made
        self.assertEqual(1, mock_create.call_count)
        self.assertEqual('test-group', mock_create.call_args[0][1])
        self.assertEqual(ids.EXPORT_GROUP_DISTRIBUTOR_ID, mock_create.call_args[0][2])
        self.assertEqual(expected_distributor_config, mock_create.call_args[0][3])

    @mock.patch('pulp_rpm.extension.admin.export.RpmGroupExportCommand.poll')
    @mock.patch('pulp.bindings.repo_groups.RepoGroupActionAPI.publish', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributor', autospec=True)
    def test_rpm_group_export_existing_task(self, mock_distributor, mock_publish, mock_poll):
        """
        Make sure that when there is already a publish operation in progress for the repository, a second
        one is not started
        """
        # Setup
        mock_distributor.return_value = (200, mock.Mock(spec=Response))
        self.mock_get_publish_tasks.return_value = 'Not None'

        # Test
        command = export.RpmGroupExportCommand(mock.MagicMock(), mock.MagicMock(),
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)
        self.assertEqual(0, mock_publish.call_count)
        mock_poll.assert_called_once_with('Not None', mock.ANY)

    @mock.patch('pulp.bindings.repo_groups.RepoGroupActionAPI.publish', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.create', autospec=True)
    @mock.patch('pulp.bindings.repo_groups.RepoGroupDistributorAPI.distributors', autospec=True)
    def test_rpm_group_export_run(self, mock_distributors, mock_create, mock_publish):
        """
        Test to make sure the publish binding is called correctly with an existing distributor.
        """
        # Setup
        mock_distributors.return_value = Response(200, [])
        mock_publish.return_value = Response(200, [])

        expected_distributor_config = {
            constants.PUBLISH_HTTP_KEYWORD: True,
            constants.PUBLISH_HTTPS_KEYWORD: True,
        }

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
        command = export.RpmGroupExportCommand(self.context, mock.MagicMock(),
                                               ids.EXPORT_GROUP_DISTRIBUTOR_ID)
        command.run(**self.kwargs)

        # Assert that the call get get the distributor was made correctly
        self.assertEqual(1, mock_distributors.call_count)
        self.assertEqual('test-group', mock_distributors.call_args[0][1])

        # Assert that when the NonFoundException is raised, a call to create a distributor is made
        self.assertEqual(1, mock_create.call_count)
        self.assertEqual('test-group', mock_create.call_args[0][1])
        self.assertEqual(ids.EXPORT_GROUP_DISTRIBUTOR_ID, mock_create.call_args[0][2])
        self.assertEqual(expected_distributor_config, mock_create.call_args[0][3])
        mock_publish.assert_called_once_with(mock.ANY, 'test-group', mock.ANY, expected_publish_config)


class TestRepoGroupExportStatusCommand(PulpClientTests):

    def setUp(self):
        super(TestRepoGroupExportStatusCommand, self).setUp()
        self.patcher = mock.patch('pulp_rpm.extension.admin.export._get_publish_tasks',
                                  spec=export._get_publish_tasks)

        self.mock_get_publish_tasks = self.patcher.start()
        self.mock_get_publish_tasks.return_value = []

    def tearDown(self):
        self.patcher.stop()

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
        # This is 2 because of the BG option provided by the polling base class
        self.assertEqual(2, mock_add_option.call_count)
        self.assertEqual(options.OPTION_GROUP_ID, mock_add_option.call_args[0][1])
        self.assertEqual('status', command.name)
        self.assertEqual(export.DESC_GROUP_EXPORT_STATUS, command.description)
        self.assertEqual(command.run, command.method)

    @mock.patch('pulp_rpm.extension.admin.export.GroupExportStatusCommand.poll')
    @mock.patch('pulp.client.commands.repo.status.status.display_task_status', autospec=True)
    def test_repo_group_export_status_run(self, mock_task_status, mock_poll):
        """
        Test the case of an existing task that should be tracked
        """
        # Setup
        self.mock_get_publish_tasks.return_value = 'task_id'
        mock_renderer = mock.Mock()

        # Test
        command = export.GroupExportStatusCommand(self.context, mock_renderer)
        command.run(**{options.OPTION_GROUP_ID.keyword: 'test-group'})

        self.mock_get_publish_tasks.assert_called_once_with('test-group', self.context)

        self.assertTrue(mock_poll.called)

    @mock.patch('pulp.client.commands.repo.status.status.display_task_status', autospec=True)
    def test_repo_group_export_status_no_task(self, mock_task_status):
        """
        Test that when no task id is found, display_task_status is not called
        """
        # Setup
        mock_renderer = mock.Mock()

        # Test
        command = export.GroupExportStatusCommand(self.context, mock_renderer)
        command.run(**{options.OPTION_GROUP_ID.keyword: 'test-group'})
        self.assertEqual(0, mock_task_status.call_count)


class TestGetPublishTasks(unittest.TestCase):
    def test_get_publish_tasks(self):
        context = mock.Mock()
        resource_id = "foo"
        result = export._get_publish_tasks(resource_id, context)
        tags = ['pulp:repository_group:foo', 'pulp:action:publish']
        criteria = {'filters': {'state': {'$nin': COMPLETED_STATES}, 'tags': {'$all': tags}}}
        self.assertTrue(context.server.tasks_search.search.called)
        created_criteria = context.server.tasks_search.search.call_args[1]
        compare_dict(criteria, created_criteria)