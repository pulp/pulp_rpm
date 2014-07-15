"""
Contains package (RPM) group management section and commands.
"""

from gettext import gettext as _

from pulp.client.commands.consumer import content as consumer_content
from pulp.client.extensions.extensions import PulpCliSection

from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP
from pulp_rpm.extensions.admin.content_schedules import YumConsumerContentCreateScheduleCommand
from pulp_rpm.extensions.admin.rpm_admin_consumer.options import FLAG_IMPORT_KEYS, FLAG_NO_COMMIT, FLAG_REBOOT

# sections ---------------------------------------------------------------------

class YumConsumerPackageGroupSection(PulpCliSection):

    def __init__(self, context):
        description = _('package group installation management')
        super(YumConsumerPackageGroupSection, self).__init__('package-group', description)

        for Section in (YumConsumerPackageGroupInstallSection,
                        YumConsumerPackageGroupUninstallSection):
            self.add_subsection(Section(context))


class YumConsumerPackageGroupInstallSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule a package group installation task')
        super(YumConsumerPackageGroupInstallSection, self).__init__('install', description)

        self.add_command(YumConsumerPackageGroupInstallCommand(context))
        self.add_subsection(YumConsumerPackageGroupSchedulesSection(context, 'install'))


class YumConsumerPackageGroupUninstallSection(PulpCliSection):

    def __init__(self, context):
        description = _('run or schedule a package group removal task')
        super(YumConsumerPackageGroupUninstallSection, self).__init__('uninstall', description)

        self.add_command(YumConsumerPackageGroupUninstallCommand(context))
        self.add_subsection(YumConsumerPackageGroupSchedulesSection(context, 'uninstall'))


class YumConsumerPackageGroupSchedulesSection(PulpCliSection):
    def __init__(self, context, action):
        description = _('manage consumer package group %s schedules' % action)
        super(YumConsumerPackageGroupSchedulesSection, self).__init__('schedules', description)

        self.add_command(consumer_content.ConsumerContentListScheduleCommand(context, action))
        self.add_command(YumConsumerContentCreateScheduleCommand(context, action, TYPE_ID_PKG_GROUP))
        self.add_command(consumer_content.ConsumerContentDeleteScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentUpdateScheduleCommand(context, action))
        self.add_command(consumer_content.NextRunCommand(context, action))

# commands ---------------------------------------------------------------------


class YumConsumerPackageGroupInstallCommand(consumer_content.ConsumerContentInstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate package group install on a consumer')
        super(YumConsumerPackageGroupInstallCommand, self).__init__(context, description=description)

    def add_content_options(self):
        self.create_option('--name',
                           _('package group name; may repeat for multiple groups'),
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
        import_keys =  kwargs[FLAG_IMPORT_KEYS.keyword]

        return {'apply': commit,
                'reboot': reboot,
                'importkeys': import_keys}

    def get_content_units(self, kwargs):

        def _unit_dict(unit_name):
            return {'type_id': TYPE_ID_PKG_GROUP,
                    'unit_key': {'name': unit_name}}

        return map(_unit_dict, kwargs['name'])

    def succeeded(self, task):

        # succeeded and failed are task-based, which is not indicative of
        # whether or not the operation succeeded or failed; that is in the
        # report stored as the task's result

        prompt = self.context.prompt
        details = task.result['details'][TYPE_ID_PKG_GROUP]['details']

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


class YumConsumerPackageGroupUninstallCommand(consumer_content.ConsumerContentUninstallCommand):

    def __init__(self, context):
        description = _('triggers an immediate package group removal on a consumer')
        super(YumConsumerPackageGroupUninstallCommand, self).__init__(context, description=description)

    def add_content_options(self):
        self.create_option('--name',
                           _('package group name; may repeat for multiple groups'),
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
            return {'type_id': TYPE_ID_PKG_GROUP,
                    'unit_key': {'name': unit_name}}

        return map(_unit_dict, kwargs['name'])

    def succeeded(self, task):

        # succeeded and failed are task-based, which is not indicative of
        # whether or not the operation succeeded or failed; that is in the
        # report stored as the task's result

        prompt = self.context.prompt
        details = task.result['details'][TYPE_ID_PKG_GROUP]['details']

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
