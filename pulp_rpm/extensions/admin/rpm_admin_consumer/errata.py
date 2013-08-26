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

from gettext import gettext as _

from pulp.client.commands.consumer import content as consumer_content
from pulp.client.extensions.extensions import PulpCliSection
from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM
from pulp_rpm.extension.admin.content_schedules import YumConsumerContentCreateScheduleCommand

from options import FLAG_IMPORT_KEYS, FLAG_NO_COMMIT, FLAG_REBOOT

# sections ---------------------------------------------------------------------

class YumConsumerErrataSection(PulpCliSection):

    def __init__(self, context):
        description = _('errata installation management')
        super(self.__class__, self).__init__('errata', description)

        self.add_subsection(YumConsumerErrataInstallSection(context))


class YumConsumerErrataInstallSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule an errata installation task')
        super(self.__class__, self).__init__('install', description)

        self.add_command(YumConsumerErrataInstallCommand(context))
        self.add_subsection(YumConsumerErrataSchedulesSection(context, 'install'))


class YumConsumerErrataSchedulesSection(PulpCliSection):

    def __init__(self, context, action):
        description = _('manage consumer errata %s schedules' % action)
        super(self.__class__, self).__init__('schedules', description)

        self.add_command(consumer_content.ConsumerContentListScheduleCommand(context, action))
        self.add_command(YumConsumerContentCreateScheduleCommand(context, action, TYPE_ID_ERRATA))
        self.add_command(consumer_content.ConsumerContentDeleteScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentUpdateScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentNextRunCommand(context, action))

# commands ---------------------------------------------------------------------

class YumConsumerErrataInstallCommand(consumer_content.ConsumerContentInstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate errata install on a consumer')
        super(YumConsumerErrataInstallCommand, self).__init__(context, description=description)

    def add_content_options(self):
        self.create_option('--errata-id',
                           _('erratum id; may repeat for multiple errata'),
                           required=True,
                           allow_multiple=True,
                           aliases=['-e'])

    def add_install_options(self):
        self.add_flag(FLAG_NO_COMMIT)
        self.add_flag(FLAG_REBOOT)
        self.add_flag(FLAG_IMPORT_KEYS)

    def get_install_options(self, kwargs):
        commit = not kwargs[FLAG_NO_COMMIT.keyword]
        reboot = kwargs[FLAG_REBOOT.keyword]
        import_keys = kwargs[FLAG_IMPORT_KEYS.keyword]

        return {'apply': commit,
                'reboot': reboot,
                'importkeys': import_keys}

    def get_content_units(self, kwargs):

        def _unit_dict(unit_id):
            return {'type_id': TYPE_ID_ERRATA,
                    'unit_key': {'id': unit_id}}

        units = map(_unit_dict, kwargs['errata-id'])
        return units

    def succeeded(self, task):
        # succeeded and failed are task-based, which is not indicative of
        # whether or not the operation succeeded or failed; that is in the
        # report stored as the task's result
        if not task.result['succeeded']:
            return self.failed(task)

        prompt = self.context.prompt
        msg = _('Install Succeeded')
        prompt.render_success_message(msg)

        # note: actually implemented on the agent as a package install so the
        # task.result will contain RPM units that were installed or updated
        # to satisfy the errata.

        if task.result['details'].has_key(TYPE_ID_RPM):
            details = task.result['details'][TYPE_ID_RPM]['details']
            resolved = details['resolved']
            fields = ['name', 'version', 'arch', 'repoid']

            if resolved:
                prompt.render_title(_('Installed'))
                prompt.render_document_list(resolved, order=fields, filters=fields)

            else:
                msg = _('Errata installed')
                prompt.render_success_message(msg)

            deps = details['deps']

            if deps:
                prompt.render_title(_('Installed for dependency'))
                prompt.render_document_list(deps, order=fields, filters=fields)

    def failed(self, task):
        """
        Called when an errata install  task has completed with a status indicating that it failed.

        :param task: full task report for the task being displayed
        :type  task: pulp.bindings.responses.Task
        """
        msg = _('Install Failed')
        self.context.prompt.render_failure_message(msg)
        try:
            message = task.result['details'][TYPE_ID_RPM]['details']['message']
            self.context.prompt.render_failure_message(message)
        except (KeyError, AttributeError, TypeError):
            #do nothing as this parameter is not always included in a failure
            pass
