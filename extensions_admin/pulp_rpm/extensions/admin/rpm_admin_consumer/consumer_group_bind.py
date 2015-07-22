from gettext import gettext as _

from pulp.bindings.exceptions import NotFoundException
from pulp.client.extensions.extensions import PulpCliCommand

YUM_DISTRIBUTOR_ID = 'yum_distributor'


class ConsumerGroupBindCommand(PulpCliCommand):
    def __init__(self, context, name, description):
        super(ConsumerGroupBindCommand, self).__init__(name, description, self.bind)

        self.create_option('--consumer-group-id', _('identifies the consumer group'), required=True)
        self.create_option('--repo-id', _('repository to bind'), required=True)

        self.context = context

    def bind(self, **kwargs):
        consumer_group_id = kwargs['consumer-group-id']
        repo_id = kwargs['repo-id']

        try:
            self.context.server.consumer_group_bind.bind(
                consumer_group_id, repo_id, YUM_DISTRIBUTOR_ID)
            m = 'Consumer Group [%(c)s] successfully bound to repository [%(r)s]'
            self.context.prompt.render_success_message(_(m) %
                                                       {'c': consumer_group_id, 'r': repo_id})
        except NotFoundException:
            m = 'Consumer Group [%(c)s] does not exist on the server'
            self.context.prompt.render_failure_message(
                _(m) % {'c': consumer_group_id}, tag='not-found')


class ConsumerGroupUnbindCommand(PulpCliCommand):
    def __init__(self, context, name, description):
        super(ConsumerGroupUnbindCommand, self).__init__(name, description, self.unbind)

        self.create_option('--consumer-group-id', _('identifies the consumer group'), required=True)
        self.create_option('--repo-id', _('repository to unbind'), required=True)

        self.context = context

    def unbind(self, **kwargs):
        consumer_group_id = kwargs['consumer-group-id']
        repo_id = kwargs['repo-id']

        try:
            self.context.server.consumer_group_bind.unbind(
                consumer_group_id, repo_id, YUM_DISTRIBUTOR_ID)
            m = 'Consumer Group [%(c)s] successfully unbound from repository [%(r)s]'
            self.context.prompt.render_success_message(_(m) %
                                                       {'c': consumer_group_id, 'r': repo_id})
        except NotFoundException, e:
            resources = e.extra_data['resources']
            if 'repo_id' in resources:
                m = 'Repository [%(r)s] does not exist on the server '
                d = {'r': repo_id}
            else:
                m = 'Consumer Group [%(c)s] does not exist on the server '
                d = {'c': consumer_group_id}
            self.context.prompt.render_failure_message(_(m) % d, tag='not-found')
