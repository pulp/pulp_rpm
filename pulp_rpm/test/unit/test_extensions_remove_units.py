# -*- coding: utf-8 -*-
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


from pulp.client.commands.unit import UnitRemoveCommand

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO,
                                 TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY)
from pulp_rpm.extension.admin import remove as remove_commands
from pulp_rpm.extension.admin.remove import BaseRemoveCommand
import rpm_support_base


class BaseRemoveCommandTests(rpm_support_base.PulpClientTests):

    def setUp(self):
        super(BaseRemoveCommandTests, self).setUp()

        self.command = BaseRemoveCommand(self.context, 'remove', 'base-remove', 'base-type')

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitRemoveCommand))


    @mock.patch('pulp_rpm.extension.admin.units_display.display_units')
    def test_succeeded(self, mock_display):
        # Setup
        fake_units = 'u'
        fake_task = mock.MagicMock()
        fake_task.result = fake_units

        # Test
        self.command.succeeded(fake_task)

        # Verify
        mock_display.assert_called_once_with(self.prompt, fake_units, self.command.unit_threshold)


class RemoveCommandsTests(rpm_support_base.PulpClientTests):
    """
    The command implementations are simply configuration to the base commands, so rather than
    re-testing the functionality of the base commands, they simply assert that the configuration
    is correct.
    """

    def test_rpm_remove_command(self):
        # Test
        command = remove_commands.RpmRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'rpm')
        self.assertEqual(command.description, remove_commands.DESC_RPM)
        self.assertEqual(command.type_id, TYPE_ID_RPM)

    def test_srpm_remove_command(self):
        # Test
        command = remove_commands.SrpmRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
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

    def test_srpm_remove_command(self):
        # Test
        command = remove_commands.SrpmRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'srpm')
        self.assertEqual(command.description, remove_commands.DESC_SRPM)
        self.assertEqual(command.type_id, TYPE_ID_SRPM)

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

    def test_distribution_remove_command(self):
        # Test
        command = remove_commands.DistributionRemoveCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, BaseRemoveCommand))
        self.assertEqual(command.name, 'distribution')
        self.assertEqual(command.description, remove_commands.DESC_DISTRIBUTION)
        self.assertEqual(command.type_id, TYPE_ID_DISTRO)
