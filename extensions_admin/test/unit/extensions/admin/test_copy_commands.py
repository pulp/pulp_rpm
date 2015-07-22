# -*- coding: utf-8 -*-

import mock
from pulp.client.commands.unit import UnitCopyCommand

from pulp_rpm.extensions.admin import copy_commands
from pulp_rpm.common.constants import CONFIG_RECURSIVE
from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_PKG_ENVIRONMENT, UNIT_KEY_RPM)
from pulp_rpm.devel.client_base import PulpClientTests


class RecursiveCopyCommandTests(PulpClientTests):
    """
    This test case isn't interested in testing the functionality of the base UnitCopyCommand
    class. It exists to test the customizations made on top of it, so don't expect there to be
    a ton going on in here.
    """

    def setUp(self):
        super(RecursiveCopyCommandTests, self).setUp()

        self.name = 'copy'
        self.description = 'fake-description'
        self.type_id = 'fake-type'
        self.command = copy_commands.RecursiveCopyCommand(self.context, self.name, self.description,
                                                          self.type_id)

    def test_structure(self):
        # Correct hierarchy of functionality
        self.assertTrue(isinstance(self.command, UnitCopyCommand))

        # Correct propagation of constructor arguments
        self.assertEqual(self.command.name, self.name)
        self.assertEqual(self.command.description, self.description)
        self.assertEqual(self.command.type_id, self.type_id)

        # Addition of the recursive flag
        self.assertTrue(copy_commands.FLAG_RECURSIVE in self.command.options)

    def test_generate_override_config(self):
        # Test
        user_input = {copy_commands.FLAG_RECURSIVE.keyword: True}
        override_config = self.command.generate_override_config(**user_input)

        # Verify
        self.assertEqual(override_config, {CONFIG_RECURSIVE: True})

    def test_generate_override_config_no_recursive(self):
        # Test
        user_input = {copy_commands.FLAG_RECURSIVE.keyword: None}
        override_config = self.command.generate_override_config(**user_input)

        # Verify
        self.assertEqual(override_config, {})


class PackageCopyCommandTests(PulpClientTests):
    """
    Simply verifies the criteria_utils is called from the overridden methods.
    """

    @mock.patch('pulp_rpm.extensions.admin.criteria_utils.parse_key_value')
    def test_key_value(self, mock_parse):
        command = copy_commands.PackageCopyCommand(self.context, 'copy', '', '')
        command._parse_key_value('foo')
        mock_parse.assert_called_once_with('foo')

    @mock.patch('pulp_rpm.extensions.admin.criteria_utils.parse_sort')
    def test_sort(self, mock_parse):
        command = copy_commands.PackageCopyCommand(self.context, 'copy', '', '')
        command._parse_sort('foo')
        mock_parse.assert_called_once_with(copy_commands.RecursiveCopyCommand, 'foo')

    @mock.patch('pulp.client.commands.unit.UnitCopyCommand.modify_user_input')
    def test_modify_user_input(self, mock_super):
        command = copy_commands.PackageCopyCommand(self.context, 'copy', '', '')
        user_input = {'a': 'a'}
        command.modify_user_input(user_input)

        # The super call is required.
        self.assertEqual(1, mock_super.call_count)

        # The user_input variable itself should be modified.
        self.assertEqual(user_input, {'a': 'a', 'fields': UNIT_KEY_RPM})

    def test_get_formatter_for_type(self):
        command = copy_commands.PackageCopyCommand(self.context, 'copy', '', '')

        # get a formatter and make sure it can be used
        formatter = command.get_formatter_for_type(TYPE_ID_RPM)
        unit_string = formatter(
            {'name': 'package1', 'version': '1.2.3', 'release': '1', 'arch': 'x86_64'})

        # make sure the name appears in the formatted string somewhere, which
        # seems like a reasonable assumption for any implementation of such
        # a formatter
        self.assertTrue(unit_string.find('package1') >= 0)


class OtherCopyCommandsTests(PulpClientTests):
    """
    Again, this test isn't concerned with testing the base command's functionality, but rather the
    correct usage of it. Given the size of the command code, rather than make a class per command, I
    lumping them all in here and doing one method per command.
    """

    def test_rpm_copy_command(self):
        # Test
        command = copy_commands.RpmCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.PackageCopyCommand))
        self.assertEqual(command.name, 'rpm')
        self.assertEqual(command.description, copy_commands.DESC_RPM)
        self.assertEqual(command.type_id, TYPE_ID_RPM)

    def test_srpm_copy_command(self):
        # Test
        command = copy_commands.SrpmCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.PackageCopyCommand))
        self.assertEqual(command.name, 'srpm')
        self.assertEqual(command.description, copy_commands.DESC_SRPM)
        self.assertEqual(command.type_id, TYPE_ID_SRPM)

    def test_drpm_copy_command(self):
        # Test
        command = copy_commands.DrpmCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.RecursiveCopyCommand))
        self.assertEqual(command.name, 'drpm')
        self.assertEqual(command.description, copy_commands.DESC_DRPM)
        self.assertEqual(command.type_id, TYPE_ID_DRPM)

    def test_errata_copy_command(self):
        # Test
        command = copy_commands.ErrataCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.RecursiveCopyCommand))
        self.assertEqual(command.name, 'errata')
        self.assertEqual(command.description, copy_commands.DESC_ERRATA)
        self.assertEqual(command.type_id, TYPE_ID_ERRATA)

    def test_distribution_copy_command(self):
        # Test
        command = copy_commands.DistributionCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.NonRecursiveCopyCommand))
        self.assertEqual(command.name, 'distribution')
        self.assertEqual(command.description, copy_commands.DESC_DISTRIBUTION)
        self.assertEqual(command.type_id, TYPE_ID_DISTRO)

    def test_group_copy_command(self):
        # Test
        command = copy_commands.PackageGroupCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.RecursiveCopyCommand))
        self.assertEqual(command.name, 'group')
        self.assertEqual(command.description, copy_commands.DESC_PKG_GROUP)
        self.assertEqual(command.type_id, TYPE_ID_PKG_GROUP)

    def test_category_copy_command(self):
        # Test
        command = copy_commands.PackageCategoryCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.RecursiveCopyCommand))
        self.assertEqual(command.name, 'category')
        self.assertEqual(command.description, copy_commands.DESC_PKG_CATEGORY)
        self.assertEqual(command.type_id, TYPE_ID_PKG_CATEGORY)

    def test_environment_copy_command(self):
        # Test
        command = copy_commands.PackageEnvironmentCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.RecursiveCopyCommand))
        self.assertEqual(command.name, 'environment')
        self.assertEqual(command.description, copy_commands.DESC_PKG_ENVIRONMENT)
        self.assertEqual(command.type_id, TYPE_ID_PKG_ENVIRONMENT)

    def test_all_copy_command(self):
        # Test
        command = copy_commands.AllCopyCommand(self.context)

        # Verify
        self.assertTrue(isinstance(command, copy_commands.NonRecursiveCopyCommand))
        self.assertEqual(command.name, 'all')
        self.assertEqual(command.description, copy_commands.DESC_ALL)
        self.assertEqual(command.type_id, None)
