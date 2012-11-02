# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

"""
Contains errata management section and commands.
"""

import time
from gettext import gettext as _
from command import PollingCommand
from pulp.client.extensions.extensions import PulpCliSection
from pulp.bindings.exceptions import NotFoundException
from pulp_rpm.extension.admin.content_schedules import (
    ContentListScheduleCommand, ContentCreateScheduleCommand, ContentDeleteScheduleCommand,
    ContentUpdateScheduleCommand, ContentNextRunCommand)
from pulp_rpm.common.ids import TYPE_ID_ERRATA


class ErrataSection(PulpCliSection):

    def __init__(self, context):
        super(__class__, self).__init__(
            'errata',
            _('errata installation management'))
        self.add_subsection(InstallSection(context))

class InstallSection(PulpCliSection):

    def __init__(self, context):
        super(__class__, self).__init__(
            'install',
            _('run or schedule an errata installation task'))

        self.add_subsection(SchedulesSection(context, 'install'))
        self.add_command(Install(context))

class SchedulesSection(PulpCliSection):
    def __init__(self, context, action):
        super(__class__, self).__init__(
            'schedules',
            _('manage consumer errata %s schedules' % action))
        self.add_command(ContentListScheduleCommand(context, action))
        self.add_command(ContentCreateScheduleCommand(context, action, content_type=TYPE_ID_ERRATA))
        self.add_command(ContentDeleteScheduleCommand(context, action))
        self.add_command(ContentUpdateScheduleCommand(context, action))
        self.add_command(ContentNextRunCommand(context, action))        

class Install(PollingCommand):

    def __init__(self, context):
        super(__class__, self).__init__(
            'run',
            _('triggers an immediate errata install on a consumer'),
            self.run,
            context)
        self.create_option(
            '--consumer-id',
            _('identifies the consumer'),
            required=True)
        self.create_flag(
            '--no-commit',
            _('transaction not committed'))
        self.create_flag(
            '--reboot',
            _('reboot after successful transaction'))
        self.create_option(
            '--errata-id',
            _('erratum id; may repeat for multiple errata'),
            required=True,
            allow_multiple=True,
            aliases=['-e'])
        self.create_flag(
            '--import-keys',
            _('import GPG keys as needed'))

    def run(self, **kwargs):
        consumer_id = kwargs['consumer-id']
        apply = (not kwargs['no-commit'])
        importkeys = kwargs['import-keys']
        reboot = kwargs['reboot']
        units = []
        options = dict(
            apply=apply,
            importkeys=importkeys,
            reboot=reboot,)
        for errata_id in kwargs['errata-id']:
            unit_key = dict(id=errata_id)
            unit = dict(type_id=TYPE_ID_ERRATA, unit_key=unit_key)
            units.append(unit)
        self.install(consumer_id, units, options)

    def install(self, consumer_id, units, options):
        prompt = self.context.prompt
        server = self.context.server
        try:
            response = server.consumer_content.install(consumer_id, units=units, options=options)
            task = response.response_body
            msg = _('Install task created with id [%s]') % task.task_id
            prompt.render_success_message(msg)
            response = server.tasks.get_task(task.task_id)
            task = response.response_body
            if self.rejected(task):
                return
            if self.postponed(task):
                return
            self.process(consumer_id, task)
        except NotFoundException:
            msg = _('Consumer [%s] not found') % consumer_id
            prompt.write(msg, tag='not-found')

    def succeeded(self, id, task):
        prompt = self.context.prompt
        # reported as failed
        if not task.result['status']:
            msg = 'Install failed'
            details = task.result['details'][TYPE_ID_ERRATA]['details']
            prompt.render_failure_message(_(msg))
            prompt.render_failure_message(details['message'])
            return
        msg = 'Install Succeeded'
        prompt.render_success_message(_(msg))
        # reported as succeeded
        if task.result['details'].has_key(TYPE_ID_ERRATA):
            details = task.result['details'][TYPE_ID_ERRATA]['details']
            filter = ['name', 'version', 'arch', 'repoid']
            resolved = details['resolved']
            if resolved:
                prompt.render_title('Installed')
                prompt.render_document_list(
                    resolved,
                    order=filter,
                    filters=filter)
            else:
                msg = 'Errata installed'
                prompt.render_success_message(_(msg))
            deps = details['deps']
            if deps:
                prompt.render_title('Installed for dependency')
                prompt.render_document_list(
                    deps,
                    order=filter,
                    filters=filter)

