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

try:
    import json
except ImportError:
    import simplejson as json

from mock import Mock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + '/../../extensions/admin')

import rpm_support_base

from rpm_admin_consumer import package, package_group, errata
from pulp.client.extensions.core import TAG_SUCCESS, TAG_FAILURE
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_PKG_GROUP


TASK = {
    'call_request_id':'TASK123',
    'call_request_group_id':None,
    'call_request_tags':{},
    'state':'finished',
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

class Task:
    def __init__(self):
        self.task_id = TASK['call_request_id']


class Request:

    def __init__(self, action):
        self.action = action

    def __call__(self, method, url, *args, **kwargs):
        if method == 'POST' and \
           url == '/pulp/api/v2/consumers/xyz/actions/content/%s/' % self.action:
            return (200, Task())
        if method == 'GET' and \
           url == '/pulp/api/v2/tasks/TASK123/':
            return (200, TASK)
        raise Exception('Unexpected URL: %s', url)


class TestPackages(rpm_support_base.PulpClientTests):

    CONSUMER_ID = 'test-consumer'

    def test_install(self):
        # Setup
        command = package.Install(self.context)
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
        self.assertEqual('GET', passed[0])
        self.assertEqual('/pulp/api/v2/tasks/TASK123/', passed[1])
        tags = self.prompt.get_write_tags()
        self.assertEqual(6, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)
        self.assertEqual(tags[5], TAG_FAILURE)

    def test_update(self):
        # Setup
        command = package.Update(self.context)
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
        self.assertEqual('GET', passed[0])
        self.assertEqual('/pulp/api/v2/tasks/TASK123/', passed[1])
        tags = self.prompt.get_write_tags()
        self.assertEqual(5, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)

    def test_uninstall(self):
        # Setup
        command = package.Uninstall(self.context)
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
        self.assertEqual('GET', passed[0])
        self.assertEqual('/pulp/api/v2/tasks/TASK123/', passed[1])
        tags = self.prompt.get_write_tags()
        self.assertEqual(5, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)



class TestGroups(rpm_support_base.PulpClientTests):

    CONSUMER_ID = 'test-consumer'

    def test_install(self):
        # Setup
        command = package_group.PackageGroupInstallCommand(self.context)
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
        self.assertEqual('GET', passed[0])
        self.assertEqual('/pulp/api/v2/tasks/TASK123/', passed[1])
        tags = self.prompt.get_write_tags()
        self.assertEqual(5, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)

    def test_uninstall(self):
        # Setup
        command = package_group.PackageGroupUninstallCommand(self.context)
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
        self.assertEqual('GET', passed[0])
        self.assertEqual('/pulp/api/v2/tasks/TASK123/', passed[1])
        tags = self.prompt.get_write_tags()
        self.assertEqual(5, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)


class TestErrata(rpm_support_base.PulpClientTests):

    def test_install(self):
        # Setup
        command = errata.Install(self.context)
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
        self.assertEqual('GET', passed[0])
        self.assertEqual('/pulp/api/v2/tasks/TASK123/', passed[1])
        tags = self.prompt.get_write_tags()
        self.assertEqual(5, len(tags))
        self.assertEqual(tags[0], TAG_SUCCESS)
