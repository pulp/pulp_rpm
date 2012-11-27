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
This code will be refactored in the 2.1 timeframe. For now, these functions
were missing from the 2.0 RPM consumer extensions and were largely copied from
the builtin implementations. There were some changes made that should be steps
towards the eventual refactoring to make these completely generic and live in
the pulp.client package.

Whoever does the final polish on these when moving to pulp.client, for the love
of root please docstring these.
"""

from gettext import gettext as _

from pulp.bindings.exceptions import NotFoundException
from pulp.client.commands.criteria import CriteriaCommand
from pulp.client.commands.options import  (OPTION_CONSUMER_ID, OPTION_NAME, OPTION_DESCRIPTION, OPTION_NOTES)
from pulp.client.extensions.extensions import (PulpCliCommand, PulpCliFlag, PulpCliOption)
from pulp.client.arg_utils import args_to_notes_dict


DESC_HISTORY = _('displays the history of operations on a consumer')
DESC_LIST = _('lists summary of consumers registered to the Pulp server')
DESC_SEARCH = _('search consumers')
DESC_UNREGISTER = _('unregisters a consumer')
DESC_UPDATE = _('changes metadata on an existing consumer')


class ListCommand(PulpCliCommand):
    def __init__(self, context, name='list', description=DESC_LIST):
        super(ListCommand, self).__init__(name, description, self.list)
        self.context = context
        self.prompt = context.prompt

        self.add_option(PulpCliFlag('--details', _('if specified, all the consumer information is displayed')))
        self.add_option(PulpCliFlag('--bindings', _('if specified, the bindings information is displayed')))
        self.add_option(PulpCliOption('--fields', _('comma-separated list of consumer fields; if specified, only the given fields will displayed'), required=False))

    def list(self, **kwargs):
        options = {}
        binding = self.context.server.consumer
        # query
        for opt in ('details', 'bindings'):
            if kwargs[opt]:
                options[opt] = kwargs[opt]
        response = binding.consumers(**options)
        # filters & ordering
        filters = ['id', 'display_name', 'description', 'bindings', 'notes']
        order = filters
        if kwargs['details']:
            order = filters[:2]
            filters = None
        elif kwargs['fields']:
            filters = kwargs['fields'].split(',')
            if 'bindings' not in filters:
                filters.append('bindings')
            if 'id' not in filters:
                filters.insert(0, 'id')
            # render
        self.prompt.render_title('Consumers')
        for c in response.response_body:
            self._format_bindings(c)
            self.prompt.render_document(c, filters=filters, order=order)

    def _format_bindings(self, consumer):
        bindings = consumer.get('bindings')
        if not bindings:
            return
        confirmed = []
        unconfirmed = []
        for binding in bindings:
            repo_id = binding['repo_id']
            if binding['deleted'] or len(binding['consumer_actions']):
                unconfirmed.append(repo_id)
            else:
                confirmed.append(repo_id)
        consumer['bindings'] = dict(confirmed=confirmed, unconfirmed=unconfirmed)


class UpdateCommand(PulpCliCommand):

    def __init__(self, context, name='update', description=DESC_UPDATE):
        super(UpdateCommand, self).__init__(name, description, self.update)
        self.context = context
        self.prompt = context.prompt

        self.add_option(OPTION_CONSUMER_ID)
        self.add_option(OPTION_NAME)
        self.add_option(OPTION_DESCRIPTION)
        self.add_option(OPTION_NOTES)

    def update(self, **kwargs):

        # Assemble the delta for all options that were passed in
        delta = dict([(k, v) for k, v in kwargs.items() if v is not None])
        delta.pop(OPTION_CONSUMER_ID.keyword) # not needed in the delta
        if OPTION_NOTES.keyword in delta.keys():
            delta['notes'] = args_to_notes_dict(delta['note'])
            delta.pop(OPTION_NOTES.keyword)
        if OPTION_NAME.keyword in delta:
            v = delta.pop(OPTION_NAME.keyword)
            key = OPTION_NAME.keyword.replace('-', '_')
            delta[key] = v

        try:
            self.context.server.consumer.update(kwargs[OPTION_CONSUMER_ID.keyword], delta)
            self.prompt.render_success_message('Consumer [%s] successfully updated' % kwargs[OPTION_CONSUMER_ID.keyword])
        except NotFoundException:
            self.prompt.write('Consumer [%s] does not exist on the server' % kwargs[OPTION_CONSUMER_ID.keyword], tag='not-found')


class UnregisterCommand(PulpCliCommand):

    def __init__(self, context, name='unregister', description=DESC_UNREGISTER):
        super(UnregisterCommand, self).__init__(name, description, self.unregister)
        self.context = context
        self.prompt = context.prompt

        self.add_option(OPTION_CONSUMER_ID)

    def unregister(self, **kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]

        try:
            self.context.server.consumer.unregister(consumer_id)
            self.prompt.render_success_message('Consumer [%s] successfully unregistered' % consumer_id)
        except NotFoundException:
            self.prompt.write('Consumer [%s] does not exist on the server' % consumer_id, tag='not-found')


class SearchCommand(CriteriaCommand):

    def __init__(self, context, name='search', description=DESC_SEARCH):
        super(SearchCommand, self).__init__(self.search, name, description, include_search=True)
        self.context = context
        self.prompt = context.prompt

    def search(self, **kwargs):
        consumer_list = self.context.server.consumer_search.search(**kwargs)
        for consumer in consumer_list:
            self.prompt.render_document(consumer)


class HistoryCommand(PulpCliCommand):

    def __init__(self, context, name='history', description=DESC_HISTORY):
        super(HistoryCommand, self).__init__(name, description, self.history)
        self.context = context
        self.prompt = context.prompt

        self.add_option(OPTION_CONSUMER_ID)
        d = _('limits displayed history entries to the given type; '
              'supported types: ("consumer_registered", "consumer_unregistered", "repo_bound", "repo_unbound",'
              '"content_unit_installed", "content_unit_uninstalled", "unit_profile_changed", "added_to_group",'
              '"removed_from_group")')
        self.add_option(PulpCliOption('--event-type', d, required=False))
        self.add_option(PulpCliOption('--limit', _('limits displayed history entries to the given amount (must be greater than zero)'), required=False))
        self.add_option(PulpCliOption('--sort', _('indicates the sort direction ("ascending" or "descending") based on the entry\'s timestamp'), required=False))
        self.add_option(PulpCliOption('--start-date', _('only return entries that occur on or after the given date in iso8601 format (yyyy-mm-ddThh:mm:ssZ)'), required=False))
        self.add_option(PulpCliOption('--end-date', _('only return entries that occur on or before the given date in iso8601 format (yyyy-mm-ddThh:mm:ssZ)'), required=False))

    def history(self, **kwargs):
        self.prompt.render_title(_('Consumer History [%(i)s]') % {'i' : kwargs[OPTION_CONSUMER_ID.keyword]})

        history_list = self.context.server.consumer_history.history(
            kwargs[OPTION_CONSUMER_ID.keyword], kwargs['event-type'], kwargs['limit'], kwargs['sort'],
            kwargs['start-date'], kwargs['end-date']).response_body
        filters = ['consumer_id', 'type', 'details', 'originator', 'timestamp']
        order = filters
        for history in history_list:
            self.prompt.render_document(history, filters=filters, order=order)
