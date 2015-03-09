
from gettext import gettext as _

from pulp.bindings.exceptions import BadRequestException, NotFoundException
from pulp.client.commands.repo.query import RepoSearchCommand
from pulp.client.consumer_utils import load_consumer_id
from pulp.client.extensions.extensions import PulpCliCommand, PulpCliOption, PulpCliFlag

from pulp_rpm.common import constants


YUM_DISTRIBUTOR_TYPE_ID = 'yum_distributor'

# -- framework hook -----------------------------------------------------------

RPM_SECTION = 'rpm'
SECTION_DESC = _('manage RPM-related features')
SEARCH_NAME = 'repos'


def initialize(context):

    if context.cli.find_section(RPM_SECTION) is not None:
        return

    rpm_section = context.cli.create_section(
        RPM_SECTION, SECTION_DESC
    )

    d = _('binds this consumer to a Pulp repository')
    rpm_section.add_command(BindCommand(context, 'bind', d))

    d = _('unbinds this consumer from a Pulp repository')
    rpm_section.add_command(UnbindCommand(context, 'unbind', d))

    rpm_section.add_command(RepoSearchCommand(context, constants.REPO_NOTE_RPM, name=SEARCH_NAME))


class BindCommand(PulpCliCommand):

    def __init__(self, context, name, description):
        PulpCliCommand.__init__(self, name, description, self.bind)
        self.context = context
        self.prompt = context.prompt

        self.add_option(PulpCliOption('--repo-id', 'repository id', required=True))

    def bind(self, **kwargs):
        consumer_id = load_consumer_id(self.context)

        if not consumer_id:
            m = _('This consumer is not registered to the Pulp server')
            self.prompt.render_failure_message(m)
            return

        repo_id = kwargs['repo-id']

        try:
            response = self.context.server.bind.bind(consumer_id, repo_id, YUM_DISTRIBUTOR_TYPE_ID)
            msg = _('Bind tasks successfully created:')
            self.context.prompt.render_success_message(msg)
            tasks = [dict(task_id=str(t.task_id)) for t in response.response_body.spawned_tasks]
            self.context.prompt.render_document_list(tasks)
        except BadRequestException, e:
            property_names = e.extra_data['property_names']
            if 'repo_id' in property_names:
                msg = _('Repository [%(r)s] does not exist on the server')
            else:
                msg = _('Repository [%(r)s] does not have a distributor')
            self.context.prompt.render_failure_message(msg % {'r': repo_id}, tag='not-found')


class UnbindCommand(PulpCliCommand):

    def __init__(self, context, name, description):
        PulpCliCommand.__init__(self, name, description, self.unbind)
        self.context = context
        self.prompt = context.prompt
        self.add_option(PulpCliOption('--repo-id', 'repository id', required=True))
        self.add_option(PulpCliFlag('--force', 'delete the binding immediately and discontinue tracking consumer actions'))

    def unbind(self, **kwargs):
        consumer_id = load_consumer_id(self.context)
        if not consumer_id:
            m = _('This consumer is not registered to the Pulp server')
            self.prompt.render_failure_message(m)
            return

        repo_id = kwargs['repo-id']
        force = kwargs['force']

        try:
            response = self.context.server.bind.unbind(consumer_id, repo_id,
                                                       YUM_DISTRIBUTOR_TYPE_ID, force)
            msg = _('Unbind tasks successfully created:')
            self.context.prompt.render_success_message(msg)
            tasks = [dict(task_id=str(t.task_id)) for t in response.response_body.spawned_tasks]
            self.context.prompt.render_document_list(tasks)
        except NotFoundException, e:
            resources = e.extra_data['resources']
            if 'repo_id' in resources:
                m = _('Repository [%(r)s] does not exist on the server')
                d = {'r': repo_id}
            else:
                m = _('Binding [consumer: %(c)s, repository: %(r)s] does not exist on the server')
                d = {
                    'c': consumer_id,
                    'r': repo_id,
                }
            self.context.prompt.render_failure_message(m % d, tag='not-found')
