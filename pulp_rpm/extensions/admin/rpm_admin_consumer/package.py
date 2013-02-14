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
Contains package (RPM) management section and commands.
"""

from gettext import gettext as _

from okaara.prompt import COLOR_RED

from pulp.bindings.exceptions import NotFoundException
from pulp.client.commands.consumer import content as consumer_content
from pulp.client.extensions.extensions import PulpCliSection
from pulp_rpm.common.ids import TYPE_ID_RPM
from pulp_rpm.extension.admin.content_schedules import YumConsumerContentCreateScheduleCommand

# progress tracker -------------------------------------------------------------

class YumConsumerPackageProgressTracker(consumer_content.ConsumerContentProgressTracker):

    def display_details(self, details):
        action = details.get('action')
        package = details.get('package')
        error = details.get('error')
        self.details = None
        if action:
            self.details = '%+12s: %s' % (action, package)
            self.prompt.write(self.details)
            return
        if error:
            action = 'Error'
            self.details = '%+12s: %s' % (action, error)
            self.prompt.write(self.details, COLOR_RED)
            return

# sections ---------------------------------------------------------------------

class YumConsumerPackageSection(PulpCliSection):

    def __init__(self, context):
        description = _('package installation management')
        super(self.__class__, self).__init__( 'package', description)

        for Section in (YumConsumerPackageInstallSection,
                        YumConsumerPackageUpdateSection,
                        YumConsumerPackageUninstallSection):
            self.add_subsection(Section(context))


class YumConsumerPackageInstallSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule a package installation task')
        super(self.__class__, self).__init__('install', description)

        self.add_command(YumConsumerPackageInstallCommand(context))
        self.add_subsection(YumConsumerSchedulesSection(context, 'install'))


class YumConsumerPackageUpdateSection(PulpCliSection):

    def __init__(self, context):
        super(self.__class__, self).__init__(
            'update',
            _('run or schedule a package update task'))

        self.add_command(YumConsumerPackageUpdateCommand(context))
        self.add_subsection(YumConsumerSchedulesSection(context, 'update'))


class YumConsumerPackageUninstallSection(PulpCliSection):

    def __init__(self, context):
        super(self.__class__, self).__init__(
            'uninstall',
            _('run or schedule a package removal task'))

        self.add_command(YumConsumerPackageUninstallCommand(context))
        self.add_subsection(YumConsumerSchedulesSection(context, 'uninstall'))


class YumConsumerSchedulesSection(PulpCliSection):
    def __init__(self, context, action):
        super(self.__class__, self).__init__(
            'schedules',
            _('manage consumer package %s schedules' % action))
        self.add_command(consumer_content.ConsumerContentListScheduleCommand(context, action))
        self.add_command(YumConsumerContentCreateScheduleCommand(context, action, TYPE_ID_RPM))
        self.add_command(consumer_content.ConsumerContentDeleteScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentUpdateScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentNextRunCommand(context, action))

# commands ---------------------------------------------------------------------

class YumConsumerPackageInstallCommand(consumer_content.ConsumerContentInstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate package install on a consumer')
        progress_tracker = YumConsumerPackageProgressTracker(context.prompt)
        super(self.__class__, self).__init__(context, description=description,
                                             progress_tracker=progress_tracker)

    def succeeded(self, id, task):
        prompt = self.context.prompt
        # reported as failed
        if not task.result['succeeded']:
            msg = 'Install failed'
            details = task.result['details'][TYPE_ID_RPM]['details']
            prompt.render_failure_message(_(msg))
            prompt.render_failure_message(details['message'])
            return
        msg = 'Install Completed'
        prompt.render_success_message(_(msg))
        # reported as succeeded
        details = task.result['details'][TYPE_ID_RPM]['details']
        filter = ['name', 'version', 'arch', 'repoid']
        resolved = details['resolved']
        if resolved:
            prompt.render_title('Installed')
            prompt.render_document_list(
                resolved,
                order=filter,
                filters=filter)
        else:
            msg = 'Packages already installed'
            prompt.render_success_message(_(msg))
        deps = details['deps']
        if deps:
            prompt.render_title('Installed for dependency')
            prompt.render_document_list(
                deps,
                order=filter,
                filters=filter)
        errors = details.get('errors', None)
        if errors:
            prompt.render_failure_message(_('Failed to install following packages:'))
            for key, value in errors.items():
                prompt.write(_('%(pkg)s : %(msg)s\n') % {'pkg': key, 'msg': value})


class YumConsumerPackageUpdateCommand(consumer_content.ConsumerContentUpdateCommand):

    def __init__(self, context):
        description = _('triggers an immediate package update on a consumer')
        progress_tracker = YumConsumerPackageProgressTracker(context.prompt)
        super(self.__class__, self).__init__(context, description=description,
                                             progress_tracker=progress_tracker)

    def update(self, consumer_id, units, options):
        prompt = self.context.prompt
        server = self.context.server
        if not units:
            msg = 'No packages specified'
            prompt.render_failure_message(_(msg))
            return
        try:
            response = server.consumer_content.update(consumer_id, units=units, options=options)
            task = response.response_body
            msg = _('Update task created with id [%(id)s]') % dict(id=task.task_id)
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

    def progress(self, report):
        self.progress_tracker.display(report)

    def succeeded(self, id, task):
        prompt = self.context.prompt
        # reported as failed
        if not task.result['succeeded']:
            msg = 'Update failed'
            details = task.result['details'][TYPE_ID_RPM]['details']
            prompt.render_failure_message(_(msg))
            prompt.render_failure_message(details['message'])
            return
        msg = 'Update Completed'
        prompt.render_success_message(_(msg))
        # reported as succeeded
        details = task.result['details'][TYPE_ID_RPM]['details']
        filter = ['name', 'version', 'arch', 'repoid']
        resolved = details['resolved']
        if resolved:
            prompt.render_title('Updated')
            prompt.render_document_list(
                resolved,
                order=filter,
                filters=filter)
        else:
            msg = 'No updates needed'
            prompt.render_success_message(_(msg))
        deps = details['deps']
        if deps:
            prompt.render_title('Installed for dependency')
            prompt.render_document_list(
                deps,
                order=filter,
                filters=filter)


class YumConsumerPackageUninstallCommand(consumer_content.ConsumerContentUninstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate package removal on a consumer')
        progress_tracker = YumConsumerPackageProgressTracker(context.prompt)
        super(self.__class__, self).__init__(context, description=description,
                                             progress_tracker=progress_tracker)

    def succeeded(self, id, task):
        prompt = self.context.prompt
        # reported as failed
        if not task.result['succeeded']:
            msg = 'Uninstall Failed'
            details = task.result['details'][TYPE_ID_RPM]['details']
            prompt.render_failure_message(_(msg))
            prompt.render_failure_message(details['message'])
            return
        msg = 'Uninstall Completed'
        prompt.render_success_message(_(msg))
        # reported as succeeded
        details = task.result['details'][TYPE_ID_RPM]['details']
        filter = ['name', 'version', 'arch', 'repoid']
        resolved = details['resolved']
        if resolved:
            prompt.render_title('Uninstalled')
            prompt.render_document_list(
                resolved,
                order=filter,
                filters=filter)
        else:
            msg = 'No matching packages found to uninstall'
            prompt.render_success_message(_(msg))
        deps = details['deps']
        if deps:
            prompt.render_title('Uninstalled for dependency')
            prompt.render_document_list(
                deps,
                order=filter,
                filters=filter)
