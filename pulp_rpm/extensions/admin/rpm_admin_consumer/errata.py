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

# sections ---------------------------------------------------------------------

class YumConsumerErrataSection(PulpCliSection):

    def __init__(self, context):
        super(self.__class__, self).__init__(
            'errata',
            _('errata installation management'))
        self.add_subsection(YumConsumerErrataInstallSection(context))


class YumConsumerErrataInstallSection(PulpCliSection):

    def __init__(self, context):
        super(self.__class__, self).__init__(
            'install',
            _('run or schedule an errata installation task'))

        self.add_command(YumConsumerErrataInstall(context))
        self.add_subsection(YumConsumerErrataSchedulesSection(context, 'install'))


class YumConsumerErrataSchedulesSection(PulpCliSection):
    def __init__(self, context, action):
        super(self.__class__, self).__init__(
            'schedules',
            _('manage consumer errata %s schedules' % action))
        self.add_command(consumer_content.ConsumerContentListScheduleCommand(context, action))
        self.add_command(YumConsumerContentCreateScheduleCommand(context, action, TYPE_ID_ERRATA))
        self.add_command(consumer_content.ConsumerContentDeleteScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentUpdateScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentNextRunCommand(context, action))

# commands ---------------------------------------------------------------------

class YumConsumerErrataInstall(consumer_content.ConsumerContentInstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate errata install on a consumer')
        super(self.__class__, self).__init__(context, description=description)

        self.options.remove(consumer_content.OPTION_CONTENT_TYPE_ID)
        self.options.remove(consumer_content.OPTION_CONTENT_UNIT)

        self.create_option(
            '--errata-id',
            _('erratum id; may repeat for multiple errata'),
            required=True,
            allow_multiple=True,
            aliases=['-e'])

    def run(self, **kwargs):
        kwargs[consumer_content.OPTION_CONTENT_TYPE_ID.keyword] = TYPE_ID_ERRATA
        kwargs[consumer_content.OPTION_CONTENT_UNIT.keyword] = kwargs['errata-id']
        super(self.__class__, self).run(**kwargs)

    def succeeded(self, id, task):
        prompt = self.context.prompt
        # reported as failed
        # note: actually implemented on the agent as a package install so the
        # task.result will contain RPM units that failed to be installed or updated.
        if not task.result['succeeded']:
            msg = _('Install failed')
            details = task.result['details'][TYPE_ID_RPM]['details']
            prompt.render_failure_message(msg)
            prompt.render_failure_message(details['message'])
            return
        msg = _('Install Succeeded')
        prompt.render_success_message(msg)
        # reported as succeeded
        # note: actually implemented on the agent as a package install so the
        # task.result will contain RPM units that were installed or updated
        # to satisfy the errata.
        if task.result['details'].has_key(TYPE_ID_RPM):
            details = task.result['details'][TYPE_ID_RPM]['details']
            filter = ['name', 'version', 'arch', 'repoid']
            resolved = details['resolved']
            if resolved:
                prompt.render_title(_('Installed'))
                prompt.render_document_list(
                    resolved,
                    order=filter,
                    filters=filter)
            else:
                msg = _('Errata installed')
                prompt.render_success_message(msg)
            deps = details['deps']
            if deps:
                prompt.render_title(_('Installed for dependency'))
                prompt.render_document_list(
                    deps,
                    order=filter,
                    filters=filter)

