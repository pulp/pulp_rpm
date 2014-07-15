"""
Contains package (RPM) management section and commands.
"""

from gettext import gettext as _

from okaara.prompt import COLOR_RED
from pulp.client.commands.consumer import content as consumer_content
from pulp.client.extensions.extensions import PulpCliSection

from pulp_rpm.common.ids import TYPE_ID_RPM
from pulp_rpm.extensions.admin.content_schedules import YumConsumerContentCreateScheduleCommand
from pulp_rpm.extensions.admin.rpm_admin_consumer.options import FLAG_IMPORT_KEYS, FLAG_NO_COMMIT, \
    FLAG_REBOOT

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
        super(YumConsumerPackageSection, self).__init__( 'package', description)

        for Section in (YumConsumerPackageInstallSection,
                        YumConsumerPackageUpdateSection,
                        YumConsumerPackageUninstallSection):
            self.add_subsection(Section(context))


class YumConsumerPackageInstallSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule a package installation task')
        super(YumConsumerPackageInstallSection, self).__init__('install', description)

        self.add_command(YumConsumerPackageInstallCommand(context))
        self.add_subsection(YumConsumerSchedulesSection(context, 'install'))


class YumConsumerPackageUpdateSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule a package update task')
        super(YumConsumerPackageUpdateSection, self).__init__('update', description)

        self.add_command(YumConsumerPackageUpdateCommand(context))
        self.add_subsection(YumConsumerSchedulesSection(context, 'update'))


class YumConsumerPackageUninstallSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule a package removal task')
        super(YumConsumerPackageUninstallSection, self).__init__('uninstall', description)

        self.add_command(YumConsumerPackageUninstallCommand(context))
        self.add_subsection(YumConsumerSchedulesSection(context, 'uninstall'))


class YumConsumerSchedulesSection(PulpCliSection):

    def __init__(self, context, action):
        description = _('manage consumer package %s schedules' % action)
        super(YumConsumerSchedulesSection, self).__init__('schedules', description)

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
        super(YumConsumerPackageInstallCommand, self).__init__(context, description=description,
                                                               progress_tracker=progress_tracker)

    def add_content_options(self):
        self.create_option('--name',
                           _('package name; may repeat for multiple packages'),
                           required=True,
                           allow_multiple=True,
                           aliases=['-n'])

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

        def _unit_dict(unit_name):
            return {'type_id': TYPE_ID_RPM,
                    'unit_key': {'name': unit_name}}

        return map(_unit_dict, kwargs['name'])

    def accepted(self, task, spinner):
        msg = _('Accepted by the agent but waiting to begin...')
        spinner.next(message=msg)

    def succeeded(self, task):

        # succeeded and failed are task-based, which is not indicative of
        # whether or not the operation succeeded or failed; that is in the
        # report stored as the task's result

        prompt = self.context.prompt
        details = task.result['details'][TYPE_ID_RPM]['details']

        if task.result['succeeded']:
            msg = _('Install Succeeded')
            prompt.render_success_message(msg)
        else:
            msg = _('Install Failed')
            prompt.render_failure_message(msg)

        # exception reported

        if 'message' in details:
            self.context.prompt.render_failure_message(details['message'])
            return

        # transaction summary

        failed = details['failed']
        resolved = details['resolved']
        installed = [p for p in resolved if p not in failed]
        deps = [p for p in details['deps'] if p not in failed]
        fields = ['name', 'version', 'arch', 'repoid']

        if not resolved:
            msg = _('Packages already installed')
            prompt.render_success_message(msg)
            return

        if installed:
            prompt.render_title(_('Installed'))
            prompt.render_document_list(installed, order=fields, filters=fields)

        if deps:
            prompt.render_title(_('Installed for Dependencies'))
            prompt.render_document_list(deps, order=fields, filters=fields)

        if failed:
            prompt.render_title(_('Failed'))
            prompt.render_document_list(failed, order=fields, filters=fields)


class YumConsumerPackageUpdateCommand(consumer_content.ConsumerContentUpdateCommand):

    def __init__(self, context):
        description = _('triggers an immediate package update on a consumer')
        progress_tracker = YumConsumerPackageProgressTracker(context.prompt)
        super(YumConsumerPackageUpdateCommand, self).__init__(context, description=description,
                                                              progress_tracker=progress_tracker)

    def add_content_options(self):
        self.create_option('--name',
                           _('package name; may repeat for multiple packages. ' +
                             'if unspecified, all packages are updated'),
                           required=False,
                           allow_multiple=True,
                           aliases=['-n'])

    def add_update_options(self):
        self.add_flag(FLAG_NO_COMMIT)
        self.add_flag(FLAG_REBOOT)
        self.add_flag(FLAG_IMPORT_KEYS)

    def get_update_options(self, kwargs):
        commit = not kwargs[FLAG_NO_COMMIT.keyword]
        reboot = kwargs[FLAG_REBOOT.keyword]
        import_keys = kwargs[FLAG_IMPORT_KEYS.keyword]
        options = {'apply': commit,
                   'reboot': reboot,
                   'importkeys': import_keys}

        if kwargs['name'] is None:
            options['all'] = True
        return options

    def get_content_units(self, kwargs):
        def _unit_dict(unit_name):
            return {'type_id': TYPE_ID_RPM,
                    'unit_key': {'name': unit_name}}

        if kwargs['name'] is not None:
            return map(_unit_dict, kwargs['name'])
        else:
            return [{'type_id': TYPE_ID_RPM, 'unit_key':None}]

    def succeeded(self, task):

        # succeeded and failed are task-based, which is not indicative of
        # whether or not the operation succeeded or failed; that is in the
        # report stored as the task's result

        prompt = self.context.prompt
        details = task.result['details'][TYPE_ID_RPM]['details']

        if task.result['succeeded']:
            msg = _('Update Succeeded')
            prompt.render_success_message(msg)
        else:
            msg = _('Update Failed')
            prompt.render_failure_message(msg)

        # exception reported

        if 'message' in details:
            self.context.prompt.render_failure_message(details['message'])
            return

        # transaction summary

        failed = details['failed']
        resolved = details['resolved']
        updated = [p for p in resolved if p not in failed]
        deps = [p for p in details['deps'] if p not in failed]
        fields = ['name', 'version', 'arch', 'repoid']

        if not resolved:
            msg = _('Packages already updated')
            prompt.render_success_message(msg)
            return

        if updated:
            prompt.render_title(_('Updated'))
            prompt.render_document_list(updated, order=fields, filters=fields)

        if deps:
            prompt.render_title(_('Updated for Dependencies'))
            prompt.render_document_list(deps, order=fields, filters=fields)

        if failed:
            prompt.render_title(_('Failed'))
            prompt.render_document_list(failed, order=fields, filters=fields)


class YumConsumerPackageUninstallCommand(consumer_content.ConsumerContentUninstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate package removal on a consumer')
        progress_tracker = YumConsumerPackageProgressTracker(context.prompt)
        super(YumConsumerPackageUninstallCommand, self).__init__(context, description=description,
                                                                 progress_tracker=progress_tracker)

    def add_content_options(self):
        self.create_option('--name',
                           _('package name; may repeat for multiple packages'),
                           required=True,
                           allow_multiple=True,
                           aliases=['-n'])

    def add_uninstall_options(self):
        self.add_flag(FLAG_NO_COMMIT)
        self.add_flag(FLAG_REBOOT)

    def get_uninstall_options(self, kwargs):
        commit = not kwargs[FLAG_NO_COMMIT.keyword]
        reboot = kwargs[FLAG_REBOOT.keyword]

        return {'apply': commit,
                'reboot': reboot}

    def get_content_units(self, kwargs):

        def _unit_dict(unit_name):
            return {'type_id': TYPE_ID_RPM,
                    'unit_key': {'name': unit_name}}

        return map(_unit_dict, kwargs['name'])

    def succeeded(self, task):

        # succeeded and failed are task-based, which is not indicative of
        # whether or not the operation succeeded or failed; that is in the
        # report stored as the task's result

        prompt = self.context.prompt
        details = task.result['details'][TYPE_ID_RPM]['details']

        if task.result['succeeded']:
            msg = _('Uninstall Succeeded')
            prompt.render_success_message(msg)
        else:
            msg = _('Uninstall Failed')
            prompt.render_failure_message(msg)

        # exception reported

        if 'message' in details:
            self.context.prompt.render_failure_message(details['message'])
            return

        # transaction summary

        failed = details['failed']
        resolved = details['resolved']
        erased = [p for p in resolved if p not in failed]
        deps = [p for p in details['deps'] if p not in failed]
        fields = ['name', 'version', 'arch', 'repoid']

        if not resolved:
            msg = _('No matching packages found to uninstall')
            prompt.render_success_message(msg)
            return

        if erased:
            prompt.render_title(_('Uninstalled'))
            prompt.render_document_list(erased, order=fields, filters=fields)

        if deps:
            prompt.render_title(_('Uninstalled for Dependencies'))
            prompt.render_document_list(deps, order=fields, filters=fields)

        if failed:
            prompt.render_title(_('Failed'))
            prompt.render_document_list(failed, order=fields, filters=fields)
