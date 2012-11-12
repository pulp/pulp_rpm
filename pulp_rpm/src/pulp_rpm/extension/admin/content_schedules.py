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
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP

# -- commands -----------------------------------------------------------------

class ContentListScheduleCommand(ListScheduleCommand):
    def __init__(self, context, action):
        strategy = ConsumerContentScheduleStrategy(context, action)
        DESC_LIST = _('list scheduled %s operations' % action)
        super(ContentListScheduleCommand, self).__init__(context, strategy,
                                                     description=DESC_LIST)
        self.add_option(OPTION_CONSUMER_ID)


class ContentCreateScheduleCommand(CreateScheduleCommand):
    def __init__(self, context, action, content_type):
        strategy = ConsumerContentScheduleStrategy(context, action, content_type)
        DESC_CREATE = _('adds a new scheduled %s operation' % action)
        super(ContentCreateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_CREATE)
        self.add_option(OPTION_CONSUMER_ID)
        assert(content_type in (TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP))
        if content_type == TYPE_ID_RPM:
            self.add_option(PulpCliOption('--name', _('package name; may be repeated for multiple packages'),
                                          required=True, allow_multiple=True, aliases=['-n']))
        elif content_type == TYPE_ID_ERRATA:
            self.add_option(PulpCliOption('--errata-id', _('erratum id; may be repeated for multiple errata'),
                                          required=True, allow_multiple=True, aliases=['-e']))
        elif content_type == TYPE_ID_PKG_GROUP:
            self.add_option(PulpCliOption('--name', _('package-group name; may be repeated for multiple package-groups'),
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

    def __init__(self, context, action, content_type=None):
        super(ConsumerContentScheduleStrategy, self).__init__()
        self.context = context
        self.action = action
        self.content_type = content_type
        self.api = context.server.consumer_content_schedules

    def create_schedule(self, schedule, failure_threshold, enabled, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        units = []
        assert(self.content_type in (TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP))
        if self.content_type in (TYPE_ID_RPM, TYPE_ID_PKG_GROUP):
            for name in kwargs['name']:
                unit_key = dict(name=name)
                unit = dict(type_id=self.content_type, unit_key=unit_key)
                units.append(unit)
        else:
            for errata_id in kwargs['errata-id']:
                unit_key = dict(id=errata_id)
                unit = dict(type_id=self.content_type, unit_key=unit_key)
                units.append(unit)

        # Eventually we'll support passing in content install arguments to the scheduled
        # call. When we do, options will be created here from kwargs.
        options = {}
        return self.api.add_schedule(self.action, consumer_id, schedule, units, failure_threshold, enabled, options)

    def delete_schedule(self, schedule_id, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        return self.api.delete_schedule(self.action, consumer_id, schedule_id)

    def retrieve_schedules(self, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        return self.api.list_schedules(self.action, consumer_id)

    def update_schedule(self, schedule_id, **kwargs):
        consumer_id = kwargs.pop(OPTION_CONSUMER_ID.keyword)
        return self.api.update_schedule(self.action, consumer_id, schedule_id, **kwargs)
