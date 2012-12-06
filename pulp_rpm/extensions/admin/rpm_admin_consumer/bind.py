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

from gettext import gettext as _

from pulp.bindings.exceptions import NotFoundException
from pulp.client.extensions.extensions import PulpCliCommand

YUM_DISTRIBUTOR_ID = 'yum_distributor'

class BindCommand(PulpCliCommand):
    def __init__(self, context, name, description):
        super(BindCommand, self).__init__(name, description, self.bind)
        self.create_option('--consumer-id', _('identifies the consumer'), required=True)
        self.create_option('--repo-id', _('repository to bind'), required=True)
        self.context = context

    def bind(self, **kwargs):
        id = kwargs['consumer-id']
        repo_id = kwargs['repo-id']

        try:
            response = self.context.server.bind.bind(id, repo_id, YUM_DISTRIBUTOR_ID)
            msg = _('Bind tasks successfully created:')
            self.context.prompt.render_success_message(msg)
            tasks = [dict(task_id=str(t.task_id)) for t in response.response_body]
            self.context.prompt.render_document_list(tasks)
        except NotFoundException, e:
            resources = e.extra_data['resources']
            if 'consumer' in resources:
                r_type = _('Consumer')
                r_id = id
            else:
                r_type = _('Repository')
                r_id = repo_id
            msg = _('%(t)s [%(id)s] does not exist on the server')
            self.context.prompt.write(msg % {'t':r_type, 'id':r_id}, tag='not-found')

class UnbindCommand(PulpCliCommand):
    def __init__(self, context, name, description):
        super(UnbindCommand, self).__init__(name, description, self.unbind)
        self.create_option('--consumer-id', _('identifies the consumer'), required=True)
        self.create_option('--repo-id', _('repository to unbind'), required=True)
        self.create_flag('--force', _('delete the binding immediately and discontinue tracking consumer actions'))
        self.context = context

    def unbind(self, **kwargs):
        id = kwargs['consumer-id']
        repo_id = kwargs['repo-id']
        force = kwargs['force']
        try:
            response = self.context.server.bind.unbind(id, repo_id, YUM_DISTRIBUTOR_ID, force)
            msg = _('Unbind tasks successfully created:')
            self.context.prompt.render_success_message(msg)
            tasks = [dict(task_id=str(t.task_id)) for t in response.response_body]
            self.context.prompt.render_document_list(tasks)
        except NotFoundException, e:
            bind_id = e.extra_data['resources']['bind_id']
            m = _('Binding [consumer: %(c)s, repository: %(r)s] does not exist on the server')
            d = {
                'c' : bind_id['consumer_id'],
                'r' : bind_id['repo_id'],
            }
            self.context.prompt.write(m % d, tag='not-found')
