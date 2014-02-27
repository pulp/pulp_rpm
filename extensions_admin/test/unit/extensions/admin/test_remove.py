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

import mock

from pulp_rpm.extensions.admin import remove as remove_commands
from pulp.client.commands.unit import UnitRemoveCommand
from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                 UNIT_KEY_RPM, TYPE_ID_PKG_ENVIRONMENT)
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extensions.admin.remove import BaseRemoveCommand, PackageRemoveCommand


class BaseRemoveCommandTests(PulpClientTests):

    def setUp(self):
        super(BaseRemoveCommandTests, self).setUp()

        self.command = BaseRemoveCommand(self.context, 'remove', 'base-remove', 'base-type')

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitRemoveCommand))

    @mock.patch('pulp_rpm.extensions.admin.units_display.get_formatter_for_type')
    def test_get_formatter_for_type(self, mock_display):
        # Setup
        fake_units = 'u'
        fake_task = mock.MagicMock()
        fake_task.result = fake_units

        # Test
        self.command.get_formatter_for_type('foo-type')

        # Verify
        mock_display.assert_called_once_with('foo-type')


class PackageRemoveCommandTests(PulpClientTests):
    """
    Simply verifies the criteria_utils is called from the overridden methods.
    """

    @mock.patch('pulp_rpm.extensions.criteria_utils.parse_key_value')
    def test_key_value(self, mock_parse):
        command = remove_commands.PackageRemoveCommand(self.context, 'copy', '', '')
        command._parse_key_value('foo')
        mock_parse.assert_called_once_with('foo')

    @mock.patch('pulp_rpm.extensions.criteria_utils.parse_sort')
    def test_sort(self, mock_parse):
        command = remove_commands.PackageRemoveCommand(self.context, 'copy', '', '')
        command._parse_sort('foo')
        mock_parse.assert_called_once_with(remove_commands.BaseRemoveCommand, 'foo')

    @mock.patch('pulp.client.commands.unit.UnitRemoveCommand.modify_user_input')
    def test_modify_user_input(self, mock_super):
        command = remove_commands.PackageRemoveCommand(self.context, 'remove', '', '')
        user_input = {'a': 'a'}
        command.modify_user_input(user_input)

        # The super call is required.
        self.assertEqual(1, mock_super.call_count)

        # The user_input variable itself should be modified.
        self.assertEqual(user_input, {'a': 'a', 'fields': UNIT_KEY_RPM})


class RemoveCommandsTests(PulpClientTests):
    """
    The command implementations are simply configuration to the base commands, so rather than
    re-testing the functionality of the base commands, they simply assert that the configuration
    is correct.
    """

    def test_rpm_remove_command(self):
        # Test
        command = remove_commands.RpmRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, PackageRemoveCommand))
        self.assertEqual(command.name, 'rpm')
        self.assertEqual(command.description, remove_commands.DESC_RPM)
        self.assertEqual(command.type_id, TYPE_ID_RPM)

    def test_srpm_remove_command(self):
        # Test
        command = remove_commands.SrpmRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, PackageRemoveCommand))
        self.assertEqual(command.name, 'srpm')
        self.assertEqual(command.description, remove_commands.DESC_SRPM)
        self.assertEqual(command.type_id, TYPE_ID_SRPM)

    def test_drpm_remove_command(self):
        # Test
        command = remove_commands.DrpmRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'drpm')
        self.assertEqual(command.description, remove_commands.DESC_DRPM)
        self.assertEqual(command.type_id, TYPE_ID_DRPM)

    def test_errata_remove_command(self):
        # Test
        command = remove_commands.ErrataRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'errata')
        self.assertEqual(command.description, remove_commands.DESC_ERRATA)
        self.assertEqual(command.type_id, TYPE_ID_ERRATA)

    def test_group_remove_command(self):
        # Test
        command = remove_commands.PackageGroupRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'group')
        self.assertEqual(command.description, remove_commands.DESC_GROUP)
        self.assertEqual(command.type_id, TYPE_ID_PKG_GROUP)

    def test_package_category_remove_command(self):
        # Test
        command = remove_commands.PackageCategoryRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'category')
        self.assertEqual(command.description, remove_commands.DESC_CATEGORY)
        self.assertEqual(command.type_id, TYPE_ID_PKG_CATEGORY)

    def test_package_environment_remove_command(self):
        # Test
        command = remove_commands.PackageEnvironmentRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'environment')
        self.assertEqual(command.description, remove_commands.DESC_ENVIRONMENT)
        self.assertEqual(command.type_id, TYPE_ID_PKG_ENVIRONMENT)

    def test_distribution_remove_command(self):
        # Test
        command = remove_commands.DistributionRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'distribution')
        self.assertEqual(command.description, remove_commands.DESC_DISTRIBUTION)
        self.assertEqual(command.type_id, TYPE_ID_DISTRO)
