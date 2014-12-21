from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.schedule import (
    DeleteScheduleCommand, ListScheduleCommand, CreateScheduleCommand,
    UpdateScheduleCommand, NextRunCommand)

from pulp_rpm.extensions.admin import sync_schedules
from pulp_rpm.devel.client_base import PulpClientTests


class StructureTests(PulpClientTests):
    def test_rpm_list_schedule_command(self):
        command = sync_schedules.RpmListScheduleCommand(self.context)

        self.assertTrue(isinstance(command, ListScheduleCommand))
        self.assertTrue(OPTION_REPO_ID in command.options)
        self.assertEqual(command.name, 'list')
        self.assertEqual(command.description, sync_schedules.DESC_LIST)

    def test_rpm_create_schedule_command(self):
        command = sync_schedules.RpmCreateScheduleCommand(self.context)

        self.assertTrue(isinstance(command, CreateScheduleCommand))
        self.assertTrue(OPTION_REPO_ID in command.options)
        self.assertEqual(command.name, 'create')
        self.assertEqual(command.description, sync_schedules.DESC_CREATE)

    def test_rpm_delete_schedule_command(self):
        command = sync_schedules.RpmDeleteScheduleCommand(self.context)

        self.assertTrue(isinstance(command, DeleteScheduleCommand))
        self.assertTrue(OPTION_REPO_ID in command.options)
        self.assertEqual(command.name, 'delete')
        self.assertEqual(command.description, sync_schedules.DESC_DELETE)

    def test_rpm_update_schedule_command(self):
        command = sync_schedules.RpmUpdateScheduleCommand(self.context)

        self.assertTrue(isinstance(command, UpdateScheduleCommand))
        self.assertTrue(OPTION_REPO_ID in command.options)
        self.assertEqual(command.name, 'update')
        self.assertEqual(command.description, sync_schedules.DESC_UPDATE)

    def test_rpm_next_run_command(self):
        command = sync_schedules.RpmNextRunCommand(self.context)

        self.assertTrue(isinstance(command, NextRunCommand))
        self.assertTrue(OPTION_REPO_ID in command.options)
        self.assertEqual(command.name, 'next')
        self.assertEqual(command.description, sync_schedules.DESC_NEXT_RUN)
