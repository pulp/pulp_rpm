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

from gettext import gettext as _

from pulp.client.commands.schedule import (
    DeleteScheduleCommand, ListScheduleCommand, CreateScheduleCommand,
    UpdateScheduleCommand, NextRunCommand, ScheduleStrategy)
from pulp.client.commands.options import OPTION_CONSUMER_ID
from pulp.client.extensions.extensions import PulpCliOption

# -- constants ----------------------------------------------------------------

TYPE_ID = 'rpm'

# -- commands -----------------------------------------------------------------

class ContentListScheduleCommand(ListScheduleCommand):
    def __init__(self, context, action):
        strategy = ConsumerContentScheduleStrategy(context, action)
        DESC_LIST = _('list scheduled %s operations' % action)
        super(ContentListScheduleCommand, self).__init__(context, strategy,
                                                     description=DESC_LIST)
        self.add_option(OPTION_CONSUMER_ID)


class ContentCreateScheduleCommand(CreateScheduleCommand):
    def __init__(self, context, action):
        strategy = ConsumerContentScheduleStrategy(context, action)
        DESC_CREATE = _('adds a new scheduled %s operation' % action)
        super(ContentCreateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_CREATE)
        self.add_option(OPTION_CONSUMER_ID)
        self.add_option(PulpCliOption('--name', _('package name; may repeat for multiple packages'),
                                      required=True, allow_multiple=True, aliases=['-n']))


class ContentDeleteScheduleCommand(DeleteScheduleCommand):
    def __init__(self, context, action):
        strategy = ConsumerContentScheduleStrategy(context, action)
        DESC_DELETE = _('deletes a %s schedule' % action)
        super(ContentDeleteScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_DELETE)
        self.add_option(OPTION_CONSUMER_ID)


class ContentUpdateScheduleCommand(UpdateScheduleCommand):
    def __init__(self, context, action):
        strategy = ConsumerContentScheduleStrategy(context, action)
        DESC_UPDATE = _('updates an existing %s schedule' % action)
        super(ContentUpdateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_UPDATE)
        self.add_option(OPTION_CONSUMER_ID)


class ContentNextRunCommand(NextRunCommand):
    def __init__(self, context, action):
        strategy = ConsumerContentScheduleStrategy(context, action)
        DESC_NEXT_RUN = _('displays the next scheduled %s for a consumer' % action)
        super(ContentNextRunCommand, self).__init__(context, strategy,
                                                description=DESC_NEXT_RUN)
        self.add_option(OPTION_CONSUMER_ID)

# -- framework classes --------------------------------------------------------

class ConsumerContentScheduleStrategy(ScheduleStrategy):

    # See super class for method documentation

    def __init__(self, context, action):
        super(ConsumerContentScheduleStrategy, self).__init__()
        self.context = context
        self.action = action
        self.api = context.server.consumer_content_schedules

    def create_schedule(self, schedule, failure_threshold, enabled, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        units = []
        for name in kwargs['name']:
            unit_key = dict(name=name)
            unit = dict(type_id=TYPE_ID, unit_key=unit_key)
            units.append(unit)
        # Eventually we'll support passing in content install arguments to the scheduled
        # call. When we do, options will be created here from kwargs.
        options = {}
        return self.api.add_schedule(self.action, consumer_id, schedule, failure_threshold, enabled, options, units)

    def delete_schedule(self, schedule_id, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        return self.api.delete_schedule(self.action, consumer_id, schedule_id)

    def retrieve_schedules(self, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        return self.api.list_schedules(self.action, consumer_id)

    def update_schedule(self, schedule_id, **kwargs):
        consumer_id = kwargs.pop(OPTION_CONSUMER_ID.keyword)
        return self.api.update_schedule(self.action, consumer_id, schedule_id, **kwargs)
