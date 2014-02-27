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
Post 2.0, commands in this module will be refactored to remove any reference to
RPM consumers and moved into the pulp.client.commands package in the platform
project. They will be needed there for when we start to handle puppet master
consumers. For now, this is the easiest approach to get this functionality
back into 2.0.
jdob, Nov 28, 2012
"""

from gettext import gettext as _

from pulp.bindings.exceptions import NotFoundException
from pulp.client import arg_utils
from pulp.client.commands.criteria import CriteriaCommand
from pulp.client.commands.options import  (OPTION_DESCRIPTION, OPTION_GROUP_ID,
                                           OPTION_NAME, OPTION_NOTES)
from pulp.client.extensions.extensions import (PulpCliCommand, PulpCliOption)


DESC_CREATE = _('creates a new consumer group')
DESC_DELETE = _('deletes a consumer group')
DESC_UPDATE = _('updates the metadata about the group itself (not its members)')
DESC_LIST   = _('lists consumer groups on the Pulp server')
DESC_SEARCH = _('searches for consumer groups on the Pulp server')

# Defaults to pass to render_document_list when displaying groups
DEFAULT_FILTERS = ['id', 'display_name', 'description', 'consumer_ids', 'notes']
DEFAULT_ORDER = DEFAULT_FILTERS


class CreateConsumerGroupCommand(PulpCliCommand):

    def __init__(self, context, name='create', description=DESC_CREATE, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(CreateConsumerGroupCommand, self).__init__(name, description, method)

        self.add_option(OPTION_GROUP_ID)
        self.add_option(OPTION_NAME)
        self.add_option(OPTION_DESCRIPTION)
        self.add_option(OPTION_NOTES)

    def run(self, **kwargs):
        # Collect input
        consumer_group_id = kwargs[OPTION_GROUP_ID.keyword]
        name = consumer_group_id
        if OPTION_NAME.keyword in kwargs:
            name = kwargs[OPTION_NAME.keyword]
        description = kwargs[OPTION_DESCRIPTION.keyword]
        notes = kwargs[OPTION_NOTES.keyword]

        # Call the server
        self.context.server.consumer_group.create(consumer_group_id, name, description, notes)

        msg = _('Consumer Group [%(group)s] successfully created')
        self.prompt.render_success_message(msg % {'group' : consumer_group_id})


class UpdateConsumerGroupCommand(PulpCliCommand):

    def __init__(self, context, name='update', description=DESC_UPDATE, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(UpdateConsumerGroupCommand, self).__init__(name, description, method)

        self.add_option(OPTION_GROUP_ID)
        self.add_option(OPTION_NAME)
        self.add_option(OPTION_DESCRIPTION)
        self.add_option(OPTION_NOTES)

    def run(self, **kwargs):
        # Assemble the delta for all options that were passed in
        delta = dict([(k, v) for k, v in kwargs.items() if v is not None])
        delta.pop(OPTION_GROUP_ID.keyword) # not needed in the delta

        if delta.pop(OPTION_NAME.keyword, None) is not None:
            delta['display_name'] = kwargs[OPTION_NAME.keyword]

        if delta.pop(OPTION_NOTES.keyword, None) is not None:
            delta['notes'] = kwargs[OPTION_NOTES.keyword]

        try:
            self.context.server.consumer_group.update(kwargs[OPTION_GROUP_ID.keyword], delta)
            msg = _('Consumer Group [%(group)s] successfully updated')
            self.prompt.render_success_message(msg % {'group' : kwargs[OPTION_GROUP_ID.keyword]})
        except NotFoundException:
            msg = _('Consumer Group [%(group)s] does not exist on the server')
            self.prompt.write(msg % {'group' : kwargs[OPTION_GROUP_ID.keyword]}, tag='not-found')


class DeleteConsumerGroupCommand(PulpCliCommand):

    def __init__(self, context, name='delete', description=DESC_DELETE, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(DeleteConsumerGroupCommand, self).__init__(name, description, method)

        self.add_option(OPTION_GROUP_ID)

    def run(self, **kwargs):
        id = kwargs[OPTION_GROUP_ID.keyword]

        try:
            self.context.server.consumer_group.delete(id)
            msg = _('Consumer Group [%(group)s] successfully deleted')
            self.prompt.render_success_message(msg % {'group' : id})
        except NotFoundException:
            msg = _('Consumer Group [%(group)s] does not exist on the server')
            self.prompt.write(msg % {'group' : id}, tag='not-found')


class ListConsumerGroupsCommand(PulpCliCommand):

    def __init__(self, context, name='list', description=DESC_LIST, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(ListConsumerGroupsCommand, self).__init__(name, description, method)

        self.add_option(PulpCliOption('--fields', _('comma-separated list of repo group fields; if specified, only the given fields will displayed'), required=False))

    def run(self, **kwargs):
        self.prompt.render_title(_('Consumer Groups'))

        consumer_group_list = self.context.server.consumer_group.consumer_groups().response_body

        # Default flags to render_document_list
        filters = DEFAULT_FILTERS
        order = DEFAULT_ORDER

        if kwargs['fields'] is not None:
            filters = kwargs['fields'].split(',')
            if 'id' not in filters:
                filters.append('id')
            order = ['id']

        self.prompt.render_document_list(consumer_group_list, filters=filters, order=order)


class SearchConsumerGroupsCommand(CriteriaCommand):

    def __init__(self, context, name='search', description=DESC_SEARCH, method=None):
        self.context = context
        self.prompt = context.prompt

        if method is None:
            method = self.run

        super(SearchConsumerGroupsCommand, self).__init__(method, name=name,
                                                          description=description,
                                                          include_search=True)

    def run(self, **kwargs):
        self.prompt.render_title(_('Consumer Groups'))

        consumer_group_list = self.context.server.consumer_group_search.search(**kwargs)
        self.prompt.render_document_list(consumer_group_list, order=DEFAULT_ORDER)
