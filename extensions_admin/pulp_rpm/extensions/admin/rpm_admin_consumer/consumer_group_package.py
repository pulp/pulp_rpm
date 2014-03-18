"""
Contains package (RPM) management section and commands.
"""

from gettext import gettext as _

from pulp.bindings.exceptions import NotFoundException
from pulp.client.commands.polling import PollingCommand
from pulp.client.extensions.extensions import PulpCliSection
from pulp.common import tags

TYPE_ID = 'rpm'


# --- utils ------------------------------------------------------------------


def get_consumer_id(task):
    for tag in task.tags:
        if not tags.is_resource_tag(tag):
            continue
        resource_type, resource_id = tags.parse_resource_tag(tag)
        if tags.RESOURCE_CONSUMER_TYPE == resource_type:
            return resource_id


# --- commands ---------------------------------------------------------------


class ConsumerGroupPackageSection(PulpCliSection):
    def __init__(self, context):
        PulpCliSection.__init__(
            self,
            'package',
            _('consumer group package installation management'))
        for Command in (ConsumerGroupInstall, ConsumerGroupUpdate,
                        ConsumerGroupUninstall):
            command = Command(context)
            command.create_option(
                '--consumer-group-id',
                _('identifies the consumer group'),
                required=True)
            command.create_flag(
                '--no-commit',
                _('transaction not committed'))
            command.create_flag(
                '--reboot',
                _('reboot after successful transaction'))
            self.add_command(command)


class ConsumerGroupInstall(PollingCommand):
    def __init__(self, context):
        PollingCommand.__init__(
            self,
            'install',
            _('install packages'),
            self.run,
            context)
        self.create_option(
            '--name',
            _('package name; may repeat for multiple packages'),
            required=True,
            allow_multiple=True,
            aliases=['-n'])
        self.create_flag(
            '--import-keys',
            _('import GPG keys as needed'))

    def run(self, **kwargs):
        consumer_group_id = kwargs['consumer-group-id']
        apply = (not kwargs['no-commit'])
        importkeys = kwargs['import-keys']
        reboot = kwargs['reboot']
        units = []
        options = dict(
            apply=apply,
            importkeys=importkeys,
            reboot=reboot, )
        for name in kwargs['name']:
            unit_key = dict(name=name)
            unit = dict(type_id=TYPE_ID, unit_key=unit_key)
            units.append(unit)
        self.install(consumer_group_id, units, options, kwargs)

    def install(self, consumer_group_id, units, options, kwargs):
        prompt = self.context.prompt
        server = self.context.server
        try:
            response = server.consumer_group_content.install(
                consumer_group_id, units=units, options=options)
            tasks = response.response_body
            self.poll(tasks, kwargs)
        except NotFoundException:
            msg = _('Consumer Group [%(g)s] not found') % {'g': consumer_group_id}
            prompt.write(msg, tag='not-found')

    def succeeded(self, task):
        prompt = self.context.prompt
        consumer_id = get_consumer_id(task)
        # reported as failed
        if not task.result['succeeded']:
            msg = _('Install on consumer [%(id)s] failed' % dict(id=consumer_id))
            details = task.result['details'][TYPE_ID]['details']
            prompt.render_failure_message(msg)
            prompt.render_failure_message(details['message'])
            return
        msg = _('Install on consumer [%(id)s] succeeded' % dict(id=consumer_id))
        prompt.render_success_message(msg)
        # reported as succeeded
        details = task.result['details'][TYPE_ID]['details']
        filter = ['name', 'version', 'arch', 'repoid']
        resolved = details['resolved']
        if resolved:
            prompt.render_title(_('Installed'))
            prompt.render_document_list(
                resolved,
                order=filter,
                filters=filter)
        else:
            msg = _('Packages already installed')
            prompt.render_success_message(msg)
        deps = details['deps']
        if deps:
            prompt.render_title(_('Installed for dependency'))
            prompt.render_document_list(
                deps,
                order=filter,
                filters=filter)


class ConsumerGroupUpdate(PollingCommand):
    def __init__(self, context):
        PollingCommand.__init__(
            self,
            'update',
            _('update (installed) packages'),
            self.run,
            context)
        self.create_option(
            '--name',
            _('package name; may repeat for multiple packages'),
            required=False,
            allow_multiple=True,
            aliases=['-n'])
        self.create_flag(
            '--import-keys',
            _('import GPG keys as needed'))
        self.create_flag(
            '--all',
            _('update all packages'),
            aliases=['-a'])

    def run(self, **kwargs):
        consumer_group_id = kwargs['consumer-group-id']
        all = kwargs['all']
        names = kwargs['name']
        apply = (not kwargs['no-commit'])
        importkeys = kwargs['import-keys']
        reboot = kwargs['reboot']
        units = []
        options = dict(
            all=all,
            apply=apply,
            importkeys=importkeys,
            reboot=reboot, )
        if all:  # ALL
            unit = dict(type_id=TYPE_ID, unit_key=None)
            self.update(consumer_group_id, [unit], options, kwargs)
            return
        if names is None:
            names = []
        for name in names:
            unit_key = dict(name=name)
            unit = dict(type_id=TYPE_ID, unit_key=unit_key)
            units.append(unit)
        self.update(consumer_group_id, units, options, kwargs)

    def update(self, consumer_group_id, units, options, kwargs):
        prompt = self.context.prompt
        server = self.context.server
        if not units:
            msg = _('No packages specified')
            prompt.render_failure_message(msg)
            return
        try:
            response = server.consumer_group_content.update(consumer_group_id, units=units,
                                                            options=options)
            tasks = response.response_body
            self.poll(tasks, kwargs)
        except NotFoundException:
            msg = _('Consumer Group [%(g)s] not found') % {'g': consumer_group_id}
            prompt.write(msg, tag='not-found')

    def succeeded(self, task):
        prompt = self.context.prompt
        consumer_id = get_consumer_id(task)
        # reported as failed
        if not task.result['succeeded']:
            msg = _('Update on consumer [%(id)s] failed' % dict(id=consumer_id))
            details = task.result['details'][TYPE_ID]['details']
            prompt.render_failure_message(msg)
            prompt.render_failure_message(details['message'])
            return
        msg = _('Update on consumer [%(id)s] succeeded' % dict(id=consumer_id))
        prompt.render_success_message(msg)
        # reported as succeeded
        details = task.result['details'][TYPE_ID]['details']
        filter = ['name', 'version', 'arch', 'repoid']
        resolved = details['resolved']
        if resolved:
            prompt.render_title(_('Updated'))
            prompt.render_document_list(
                resolved,
                order=filter,
                filters=filter)
        else:
            msg = _('No updates needed')
            prompt.render_success_message(msg)
        deps = details['deps']
        if deps:
            prompt.render_title(_('Installed for dependency'))
            prompt.render_document_list(
                deps,
                order=filter,
                filters=filter)


class ConsumerGroupUninstall(PollingCommand):
    def __init__(self, context):
        PollingCommand.__init__(
            self,
            'uninstall',
            _('uninstall packages'),
            self.run,
            context)
        self.create_option(
            '--name',
            _('package name; may repeat for multiple packages'),
            required=True,
            allow_multiple=True,
            aliases=['-n'])

    def run(self, **kwargs):
        consumer_group_id = kwargs['consumer-group-id']
        apply = (not kwargs['no-commit'])
        reboot = kwargs['reboot']
        units = []
        options = dict(
            apply=apply,
            reboot=reboot, )
        for name in kwargs['name']:
            unit_key = dict(name=name)
            unit = dict(type_id=TYPE_ID, unit_key=unit_key)
            units.append(unit)
        self.uninstall(consumer_group_id, units, options, kwargs)

    def uninstall(self, consumer_group_id, units, options, kwargs):
        prompt = self.context.prompt
        server = self.context.server
        try:
            response = server.consumer_group_content.uninstall(consumer_group_id, units=units,
                                                               options=options)
            tasks = response.response_body
            self.poll(tasks, kwargs)
        except NotFoundException:
            msg = _('Consumer Group [%s] not found') % consumer_group_id
            prompt.write(msg, tag='not-found')

    def succeeded(self, task):
        prompt = self.context.prompt
        consumer_id = get_consumer_id(task)
        # reported as failed
        if not task.result['succeeded']:
            msg = _('Install on consumer [%(id)s] failed' % dict(id=consumer_id))
            details = task.result['details'][TYPE_ID]['details']
            prompt.render_failure_message(msg)
            prompt.render_failure_message(details['message'])
            return
        msg = _('Uninstall on consumer [%(id)s] succeeded' % dict(id=consumer_id))
        prompt.render_success_message(msg)
        # reported as succeeded
        details = task.result['details'][TYPE_ID]['details']
        filter = ['name', 'version', 'arch', 'repoid']
        resolved = details['resolved']
        if resolved:
            prompt.render_title('Uninstalled')
            prompt.render_document_list(
                resolved,
                order=filter,
                filters=filter)
        else:
            msg = _('No matching packages found to uninstall')
            prompt.render_success_message(msg)
        deps = details['deps']
        if deps:
            prompt.render_title(_('Uninstalled for dependency'))
            prompt.render_document_list(
                deps,
                order=filter,
                filters=filter)
