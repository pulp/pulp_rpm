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
from pulp.client.commands import options

from pulp_rpm.common import ids
from pulp_rpm.extension.admin import export, status
import rpm_support_base


class TestRepoExportRunCommand(rpm_support_base.PulpClientTests):
    """
    Tests the rpm repo export run command. This makes use of the platform RunPublishRepositoryCommand,
    so all that's tested here is that the constructor is called correctly.
    """

    @mock.patch('pulp.client.commands.repo.sync_publish.RunPublishRepositoryCommand.__init__', autospec=True)
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
    @mock.patch('pulp.client.extensions.extensions.PulpCliCommand.create_flag', autospec=True)
    @mock.patch('okaara.cli.Command.add_option', autospec=True)
    def test_rpm_group_export_run_setup(self, mock_add_option, mock_create_flag):
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

    def test_rpm_group_export_run(self):
        pass


class TestRepoGroupExportStatusCommand(rpm_support_base.PulpClientTests):
    pass