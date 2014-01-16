# Copyright (c) 2012 Red Hat, Inc.
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
from pulp_rpm.devel import rpm_support_base

from pulp.client.commands.consumer.content import OPTION_CONTENT_TYPE_ID, OPTION_CONTENT_UNIT
from pulp.client.commands.options import OPTION_CONSUMER_ID
from pulp.client.commands.schedule import CreateScheduleCommand
from pulp_rpm.devel.client_base import PulpClientTests

from pulp_rpm.extension.admin.content_schedules import (
    YumConsumerContentCreateScheduleCommand, YumConsumerContentScheduleStrategy)
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_PKG_GROUP, TYPE_ID_ERRATA

SCHEDULE_INSTALL_ACTIONS = ('install', 'uninstall', 'update')

class StructureTests(PulpClientTests):

    def test_rpm_create_schedule_command(self):
        for content_type in (TYPE_ID_RPM, TYPE_ID_PKG_GROUP, TYPE_ID_ERRATA):
            for action in SCHEDULE_INSTALL_ACTIONS:
                command = YumConsumerContentCreateScheduleCommand(self.context, action=action,
                                                                  content_type=content_type)

                self.assertTrue(isinstance(command, CreateScheduleCommand))
                self.assertTrue(OPTION_CONSUMER_ID in command.options)
                self.assertTrue(OPTION_CONTENT_TYPE_ID not in command.options)
                self.assertTrue(OPTION_CONTENT_UNIT not in command.options)
                self.assertEqual(command.name, 'create')
                self.assertTrue(action in command.description)


class ConsumerContentInstallScheduleStrategyTests(PulpClientTests):

    def setUp(self):
        super(ConsumerContentInstallScheduleStrategyTests, self).setUp()
        self.strategy = YumConsumerContentScheduleStrategy(self.context, 'install', TYPE_ID_RPM)

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.add_schedule')
    def test_create_schedule(self, mock_add):
        # Setup
        schedule = '2012-09-18'
        failure_threshold = 3
        enabled = True
        kwargs = {OPTION_CONSUMER_ID.keyword : 'test-consumer',
                  'name': ['pkg1','pkg2']}

        # Test
        self.strategy.create_schedule(schedule, failure_threshold, enabled, kwargs)

        # Verify
        self.assertEqual(1, mock_add.call_count)
        call_args = mock_add.call_args[0]
        self.assertEqual('install', call_args[0])
        self.assertEqual('test-consumer', call_args[1])
        self.assertEqual(schedule, call_args[2])
        self.assertEqual(failure_threshold, call_args[4])
        self.assertEqual(enabled, call_args[5])
        self.assertEqual({}, call_args[6])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.delete_schedule')
    def test_delete_schedule(self, mock_delete):
        # Setup
        schedule_id = 'fake-schedule'
        kwargs = {OPTION_CONSUMER_ID.keyword : 'fake-consumer'}

        # Test
        self.strategy.delete_schedule(schedule_id, kwargs)

        # Verify
        self.assertEqual(1, mock_delete.call_count)
        call_args = mock_delete.call_args[0]
        self.assertEqual('install', call_args[0])
        self.assertEqual('fake-consumer', call_args[1])
        self.assertEqual(schedule_id, call_args[2])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.list_schedules')
    def test_retrieve_schedules(self, mock_retrieve):
        # Setup
        kwargs = {OPTION_CONSUMER_ID.keyword : 'retrieve-consumer'}

        # Test
        self.strategy.retrieve_schedules(kwargs)

        # Verify
        self.assertEqual(1, mock_retrieve.call_count)
        call_args = mock_retrieve.call_args[0]
        self.assertEqual('install', call_args[0])
        self.assertEqual('retrieve-consumer', call_args[1])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.update_schedule')
    def test_update_schedule(self, mock_update):
        # Setup
        kwargs = {OPTION_CONSUMER_ID.keyword : 'fake-consumer', 'a' : 'a'}
        schedule_id = 'schedule-id'

        # Test
        self.strategy.update_schedule(schedule_id, **kwargs)

        # Verify
        self.assertEqual(1, mock_update.call_count)
        call_args = mock_update.call_args[0]
        self.assertEqual('install', call_args[0])
        self.assertEqual('fake-consumer', call_args[1])
        self.assertEqual(schedule_id, call_args[2])
        call_kwargs = mock_update.call_args[1]
        self.assertEqual({'a' : 'a'}, call_kwargs)


class ConsumerContentUninstallScheduleStrategyTests(PulpClientTests):

    def setUp(self):
        super(ConsumerContentUninstallScheduleStrategyTests, self).setUp()
        self.strategy = YumConsumerContentScheduleStrategy(self.context, 'uninstall', TYPE_ID_RPM)

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.add_schedule')
    def test_create_schedule(self, mock_add):
        # Setup
        schedule = '2012-09-18'
        failure_threshold = 3
        enabled = True
        kwargs = {OPTION_CONSUMER_ID.keyword : 'test-consumer',
                  'name': ['pkg1','pkg2']}

        # Test
        self.strategy.create_schedule(schedule, failure_threshold, enabled, kwargs)

        # Verify
        self.assertEqual(1, mock_add.call_count)
        call_args = mock_add.call_args[0]
        self.assertEqual('uninstall', call_args[0])
        self.assertEqual('test-consumer', call_args[1])
        self.assertEqual(schedule, call_args[2])
        self.assertEqual(failure_threshold, call_args[4])
        self.assertEqual(enabled, call_args[5])
        self.assertEqual({}, call_args[6])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.delete_schedule')
    def test_delete_schedule(self, mock_delete):
        # Setup
        schedule_id = 'fake-schedule'
        kwargs = {OPTION_CONSUMER_ID.keyword : 'fake-consumer'}

        # Test
        self.strategy.delete_schedule(schedule_id, kwargs)

        # Verify
        self.assertEqual(1, mock_delete.call_count)
        call_args = mock_delete.call_args[0]
        self.assertEqual('uninstall', call_args[0])
        self.assertEqual('fake-consumer', call_args[1])
        self.assertEqual(schedule_id, call_args[2])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.list_schedules')
    def test_retrieve_schedules(self, mock_retrieve):
        # Setup
        kwargs = {OPTION_CONSUMER_ID.keyword : 'retrieve-consumer'}

        # Test
        self.strategy.retrieve_schedules(kwargs)

        # Verify
        self.assertEqual(1, mock_retrieve.call_count)
        call_args = mock_retrieve.call_args[0]
        self.assertEqual('uninstall', call_args[0])
        self.assertEqual('retrieve-consumer', call_args[1])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.update_schedule')
    def test_update_schedule(self, mock_update):
        # Setup
        kwargs = {OPTION_CONSUMER_ID.keyword : 'fake-consumer', 'a' : 'a'}
        schedule_id = 'schedule-id'

        # Test
        self.strategy.update_schedule(schedule_id, **kwargs)

        # Verify
        self.assertEqual(1, mock_update.call_count)
        call_args = mock_update.call_args[0]
        self.assertEqual('uninstall', call_args[0])
        self.assertEqual('fake-consumer', call_args[1])
        self.assertEqual(schedule_id, call_args[2])
        call_kwargs = mock_update.call_args[1]
        self.assertEqual({'a' : 'a'}, call_kwargs)


class ConsumerContentUpdateScheduleStrategyTests(PulpClientTests):

    def setUp(self):
        super(ConsumerContentUpdateScheduleStrategyTests, self).setUp()
        self.strategy = YumConsumerContentScheduleStrategy(self.context, 'update', TYPE_ID_RPM)

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.add_schedule')
    def test_create_schedule(self, mock_add):
        # Setup
        schedule = '2012-09-18'
        failure_threshold = 3
        enabled = True
        kwargs = {OPTION_CONSUMER_ID.keyword : 'test-consumer',
                  'name': ['pkg1','pkg2']}

        # Test
        self.strategy.create_schedule(schedule, failure_threshold, enabled, kwargs)

        # Verify
        self.assertEqual(1, mock_add.call_count)
        call_args = mock_add.call_args[0]
        self.assertEqual('update', call_args[0])
        self.assertEqual('test-consumer', call_args[1])
        self.assertEqual(schedule, call_args[2])
        self.assertEqual(failure_threshold, call_args[4])
        self.assertEqual(enabled, call_args[5])
        self.assertEqual({}, call_args[6])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.delete_schedule')
    def test_delete_schedule(self, mock_delete):
        # Setup
        schedule_id = 'fake-schedule'
        kwargs = {OPTION_CONSUMER_ID.keyword : 'fake-consumer'}

        # Test
        self.strategy.delete_schedule(schedule_id, kwargs)

        # Verify
        self.assertEqual(1, mock_delete.call_count)
        call_args = mock_delete.call_args[0]
        self.assertEqual('update', call_args[0])
        self.assertEqual('fake-consumer', call_args[1])
        self.assertEqual(schedule_id, call_args[2])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.list_schedules')
    def test_retrieve_schedules(self, mock_retrieve):
        # Setup
        kwargs = {OPTION_CONSUMER_ID.keyword : 'retrieve-consumer'}

        # Test
        self.strategy.retrieve_schedules(kwargs)

        # Verify
        self.assertEqual(1, mock_retrieve.call_count)
        call_args = mock_retrieve.call_args[0]
        self.assertEqual('update', call_args[0])
        self.assertEqual('retrieve-consumer', call_args[1])

    @mock.patch('pulp.bindings.consumer.ConsumerContentSchedulesAPI.update_schedule')
    def test_update_schedule(self, mock_update):
        # Setup
        kwargs = {OPTION_CONSUMER_ID.keyword : 'fake-consumer', 'a' : 'a'}
        schedule_id = 'schedule-id'

        # Test
        self.strategy.update_schedule(schedule_id, **kwargs)

        # Verify
        self.assertEqual(1, mock_update.call_count)
        call_args = mock_update.call_args[0]
        self.assertEqual('update', call_args[0])
        self.assertEqual('fake-consumer', call_args[1])
        self.assertEqual(schedule_id, call_args[2])
        call_kwargs = mock_update.call_args[1]
        self.assertEqual({'a' : 'a'}, call_kwargs)

