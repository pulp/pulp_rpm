#!/usr/bin/python
#
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

import os
import sys

from mock import Mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + '/../../extensions/admin')

import rpm_support_base

from pulp.bindings.responses import STATE_FINISHED
from pulp.bindings.tasks import Task
from pulp.client.extensions.core import TAG_SUCCESS
from pulp.devel.unit.task_simulator import TaskSimulator
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_PKG_GROUP

from rpm_admin_consumer import package, package_group, errata

TASK = {
    'call_request_id':'TASK123',
    'call_request_group_id':None,
    'call_request_tags':{},
    'state':'waiting',
    'start_time':None,
    'finish_time':None,
    'progress':None,
    'exception':None,
    'traceback':None,
    'response':None,
    'reasons':None,
    'result':{
        'succeeded':True,
        'reboot_scheduled':False,
        'details':{
            TYPE_ID_RPM:{
                'succeeded':True,
                'details':{
                   'resolved':[
                        {'name':'zsh-1.0'}],
                   'deps':[],
                   'errors':{
                        'fail-test': 'No package(s) available to install'
                    },
                }
            },
            TYPE_ID_PKG_GROUP:{
                'succeeded':True,
                'details':{
                   'resolved':[
                        {'name':'zsh-1.0'}],
                   'deps':[]
                }
            }
         }
     }
}


class Request:

    def __init__(self, action):
        self.action = action

    def __call__(self, method, url, *args, **kwargs):
        if method == 'POST' and \
           url == '/pulp/api/v2/consumers/xyz/actions/content/%s/' % self.action:
            return (200, Task(TASK))
        if method == 'GET' and \
           url == '/pulp/api/v2/tasks/TASK123/':
            return (200, TASK)
        raise Exception('Unexpected URL: %s', url)


class TestPackages(rpm_support_base.PulpClientTests):

    CONSUMER_ID = 'test-consumer'

    def test_install(self):
        # Setup
        sim = TaskSimulator()
        sim.install(self.bindings)

        progress_report = {'steps' : [], 'details' : {}}
        final_task = sim.add_task_state('TASK123', STATE_FINISHED)
        final_task.progress = progress_report
        final_task.result = TASK['result']

        command = package.YumConsumerPackageInstallCommand(self.context)
        self.server_mock.request = Mock(side_effect=Request('install'))
        # Test
        args = {
            'consumer-id':'xyz',
            'name':['zsh','fail-test'],
            'no-commit':False,
            'import-keys':False,
            'reboot':False,
        }
        command.run(**args)

        # Verify
        passed = self.server_mock.request.call_args[0]
        self.assertEqual('POST', passed[0])
        tags = self.prompt.get_write_tags()
        self.assertEqual(7, len(tags))

    def test_update(self):
        # Setup
        sim = TaskSimulator()
        sim.install(self.bindings)

        progress_report = {'steps' : [], 'details' : {}}
        final_task = sim.add_task_state('TASK123', STATE_FINISHED)
        final_task.progress = progress_report
        final_task.result = TASK['result']

        command = package.YumConsumerPackageUpdateCommand(self.context)
        self.server_mock.request = Mock(side_effect=Request('update'))
        # Test
        args = {
            'consumer-id':'xyz',
            'name':['zsh'],
            'no-commit':False,
            'import-keys':False,
            'reboot':False,
            'all':False,
        }
        command.run(**args)

        # Verify
        passed = self.server_mock.request.call_args[0]
        self.assertEqual('POST', passed[0])
        tags = self.prompt.get_write_tags()
        self.assertEqual(7, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)

    def test_uninstall(self):
        # Setup
        sim = TaskSimulator()
        sim.install(self.bindings)

        progress_report = {'steps' : [], 'details' : {}}
        final_task = sim.add_task_state('TASK123', STATE_FINISHED)
        final_task.progress = progress_report
        final_task.result = TASK['result']

        command = package.YumConsumerPackageUninstallCommand(self.context)
        self.server_mock.request = Mock(side_effect=Request('uninstall'))
        # Test
        args = {
            'consumer-id':'xyz',
            'name':['zsh'],
            'no-commit':False,
            'importkeys':False,
            'reboot':False,
        }
        command.run(**args)

        # Verify
        passed = self.server_mock.request.call_args[0]
        self.assertEqual('POST', passed[0])
        tags = self.prompt.get_write_tags()
        self.assertEqual(7, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)


class TestGroups(rpm_support_base.PulpClientTests):

    CONSUMER_ID = 'test-consumer'

    def test_install(self):
        # Setup
        sim = TaskSimulator()
        sim.install(self.bindings)

        progress_report = {'steps' : [], 'details' : {}}
        final_task = sim.add_task_state('TASK123', STATE_FINISHED)
        final_task.progress = progress_report
        final_task.result = TASK['result']

        command = package_group.YumConsumerPackageGroupInstallCommand(self.context)
        self.server_mock.request = Mock(side_effect=Request('install'))
        # Test
        args = {
            'consumer-id':'xyz',
            'name':['Test Group'],
            'no-commit':False,
            'import-keys':False,
            'reboot':False,
        }
        command.run(**args)

        # Verify
        passed = self.server_mock.request.call_args[0]
        self.assertEqual('POST', passed[0])
        tags = self.prompt.get_write_tags()
        self.assertEqual(6, len(tags))

    def test_uninstall(self):
        # Setup
        sim = TaskSimulator()
        sim.install(self.bindings)

        progress_report = {'steps' : [], 'details' : {}}
        final_task = sim.add_task_state('TASK123', STATE_FINISHED)
        final_task.progress = progress_report
        final_task.result = TASK['result']

        command = package_group.YumConsumerPackageGroupUninstallCommand(self.context)
        self.server_mock.request = Mock(side_effect=Request('uninstall'))
        # Test
        args = {
            'consumer-id':'xyz',
            'name':['Test Group'],
            'no-commit':False,
            'importkeys':False,
            'reboot':False,
        }
        command.run(**args)

        # Verify
        passed = self.server_mock.request.call_args[0]
        self.assertEqual('POST', passed[0])
        tags = self.prompt.get_write_tags()
        self.assertEqual(7, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)


class TestErrata(rpm_support_base.PulpClientTests):

    def test_install(self):
        # Setup
        sim = TaskSimulator()
        sim.install(self.bindings)

        progress_report = {'steps' : [], 'details' : {}}
        final_task = sim.add_task_state('TASK123', STATE_FINISHED)
        final_task.progress = progress_report
        final_task.result = TASK['result']

        command = errata.YumConsumerErrataInstallCommand(self.context)
        self.server_mock.request = Mock(side_effect=Request('install'))
        # Test
        args = {
            'consumer-id':'xyz',
            'errata-id':'MY-ERRATA',
            'no-commit':False,
            'import-keys':False,
            'reboot':False,
        }
        command.run(**args)

        # Verify
        passed = self.server_mock.request.call_args[0]
        self.assertEqual('POST', passed[0])
        tags = self.prompt.get_write_tags()
        self.assertEqual(6, len(tags))
