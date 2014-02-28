# -*- coding: utf-8 -*-
# Copyright (c) 2012 Red Hat, Inc.
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
Post 2.0, commands in this module will be refactored to remove any reference to
RPM consumers and moved into the pulp.client.commands package in the platform
project. They will be needed there for when we start to handle puppet master
consumers. For now, this is the easiest approach to get this functionality
back into 2.0.

In fact, I suspect a lot of this code will be refactored into a generic "group
membership" series of commands. Again, with 2.0 so close, I'd rather not bite
off the risk of refactoring the repo group membership commands, so there
are concepts duplicated here.

jdob, Nov 28, 2012
"""

import copy
from gettext import gettext as _

from pulp.client.commands.criteria import CriteriaCommand
from pulp.client.commands.options import  (OPTION_GROUP_ID, FLAG_ALL, OPTION_CONSUMER_ID)
from pulp.client.extensions.extensions import PulpCliCommand
from pulp.common import compat


DESC_LIST = _('list the consumers in a particular group')
DESC_ADD = _('add consumers to an existing group')
DESC_REMOVE = _('remove consumers from a group')


class ListConsumerGroupMembersCommand(PulpCliCommand):

    def __init__(self, context, name='list', description=DESC_LIST, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(ListConsumerGroupMembersCommand, self).__init__(name, description,
                                                              method)

        self.add_option(OPTION_GROUP_ID)

    def run(self, **kwargs):
        self.prompt.render_title(_('Consumer Group Members'))

        consumer_group_id = kwargs[OPTION_GROUP_ID.keyword]
        criteria = {'fields':('consumer_ids',),
                    'filters':{'id':consumer_group_id}}

        consumer_group_list = self.context.server.consumer_group_search.search(**criteria)

        if len(consumer_group_list) != 1:
            msg = _('Consumer group [%(g)s] does not exist on the server')
            self.prompt.render_failure_message(msg % {'g' : consumer_group_id}, tag='not-found')
        else:
            consumer_ids = consumer_group_list[0].get('consumer_ids')
            if consumer_ids:
                criteria = {'filters':{'id':{'$in':consumer_ids}}}
                consumer_list = self.context.server.consumer_search.search(**criteria)

                filters = ['id', 'display_name', 'description', 'notes']
                order = filters

                self.prompt.render_document_list(consumer_list, filters=filters, order=order)


class ConsumerGroupMembersCommand(CriteriaCommand):
    """
    This class is very similar to pulp.client.commands.repo.group.RepositoryGroupMembersCommand.
    Post 2.0 that class should be refactored to be a base for all group membership
    commands, but I'm not willing to take on the risk or time investment right
    now.
    jdob, Dec 4, 2012
    """

    def __init__(self, context, name, description, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(ConsumerGroupMembersCommand, self).__init__(
            method, name, description, include_search=False
        )

        self.add_option(OPTION_GROUP_ID)
        self.add_flag(FLAG_ALL)

        # Copy the consumer ID option so we can dork with it
        consumer_id_option = copy.copy(OPTION_CONSUMER_ID)
        consumer_id_option.required = False
        consumer_id_option.allow_multiple = True
        self.add_option(consumer_id_option)

    def run(self, **kwargs):
        group_id = kwargs.pop(OPTION_GROUP_ID.keyword)
        if not compat.any(kwargs.values()):
            self.prompt.render_failure_message(
                _('At least one matching option must be provided.'))
            return
        kwargs.pop(FLAG_ALL.keyword, None)

        consumer_ids = kwargs.pop(OPTION_CONSUMER_ID.keyword)
        if consumer_ids:
            in_arg = kwargs.get('in') or []
            in_arg.append(('id', ','.join(consumer_ids)))
            kwargs['in'] = in_arg

        self._action(group_id, **kwargs)

    def _action(self, group_id, **kwargs):
        """
        Override this in base classes. It should call an appropriate remote
        method to execute an action.

        :param group_id:    primary key for a repo group
        :type  group_id:    str
        """
        raise NotImplementedError


class AddConsumerGroupMembersCommand(ConsumerGroupMembersCommand):

    def __init__(self, context, name='add', description=DESC_ADD, method=None):
        super(AddConsumerGroupMembersCommand, self).__init__(
            context, name, description, method
        )

    def _action(self, group_id, **kwargs):
        self.context.server.consumer_group_actions.associate(group_id, **kwargs)
        msg = _('Consumer Group [%(c)s] membership updated')
        self.context.prompt.render_success_message(msg % {'c' : group_id})


class RemoveConsumerGroupMembersCommand(ConsumerGroupMembersCommand):

    def __init__(self, context, name='remove', description=DESC_REMOVE, method=None):
        super(RemoveConsumerGroupMembersCommand, self).__init__(
            context, name, description, method
        )

    def _action(self, group_id, **kwargs):
        self.context.server.consumer_group_actions.unassociate(group_id, **kwargs)
        msg = _('Consumer Group [%(c)s] membership updated')
        self.context.prompt.render_success_message(msg % {'c' : group_id})
