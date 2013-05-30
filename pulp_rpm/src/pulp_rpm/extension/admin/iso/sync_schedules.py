# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
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
from pulp.client.commands.options import OPTION_REPO_ID

from pulp_rpm.common.ids import TYPE_ID_IMPORTER_ISO

# -- constants ----------------------------------------------------------------

DESC_LIST = _('list scheduled sync operations')
DESC_CREATE = _('add new scheduled sync operations')
DESC_DELETE = _('delete sync schedules')
DESC_UPDATE = _('update existing schedules')
DESC_NEXT_RUN = _('display the next scheduled sync run for a repository')

# -- commands -----------------------------------------------------------------

class ISOListScheduleCommand(ListScheduleCommand):
    def __init__(self, context):
        strategy = RepoSyncScheduleStrategy(context)
        super(ISOListScheduleCommand, self).__init__(context, strategy,
                                                     description=DESC_LIST)
        self.add_option(OPTION_REPO_ID)


class ISOCreateScheduleCommand(CreateScheduleCommand):
    def __init__(self, context):
        strategy = RepoSyncScheduleStrategy(context)
        super(ISOCreateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_CREATE)
        self.add_option(OPTION_REPO_ID)


class ISODeleteScheduleCommand(DeleteScheduleCommand):
    def __init__(self, context):
        strategy = RepoSyncScheduleStrategy(context)
        super(ISODeleteScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_DELETE)
        self.add_option(OPTION_REPO_ID)


class ISOUpdateScheduleCommand(UpdateScheduleCommand):
    def __init__(self, context):
        strategy = RepoSyncScheduleStrategy(context)
        super(ISOUpdateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_UPDATE)
        self.add_option(OPTION_REPO_ID)


class ISONextRunCommand(NextRunCommand):
    def __init__(self, context):
        strategy = RepoSyncScheduleStrategy(context)
        super(ISONextRunCommand, self).__init__(context, strategy,
                                                description=DESC_NEXT_RUN)
        self.add_option(OPTION_REPO_ID)

# -- framework classes --------------------------------------------------------

class RepoSyncScheduleStrategy(ScheduleStrategy):

    # See super class for method documentation

    def __init__(self, context):
        super(RepoSyncScheduleStrategy, self).__init__()
        self.context = context
        self.api = context.server.repo_sync_schedules

    def create_schedule(self, schedule, failure_threshold, enabled, kwargs):
        repo_id = kwargs[OPTION_REPO_ID.keyword]

        # Eventually we'll support passing in sync arguments to the scheduled
        # call. When we do, override_config will be created here from kwargs.
        override_config = {}

        return self.api.add_schedule(repo_id, TYPE_ID_IMPORTER_ISO, schedule, override_config,
                                     failure_threshold, enabled)

    def delete_schedule(self, schedule_id, kwargs):
        repo_id = kwargs[OPTION_REPO_ID.keyword]
        return self.api.delete_schedule(repo_id, TYPE_ID_IMPORTER_ISO, schedule_id)

    def retrieve_schedules(self, kwargs):
        repo_id = kwargs[OPTION_REPO_ID.keyword]
        return self.api.list_schedules(repo_id, TYPE_ID_IMPORTER_ISO)

    def update_schedule(self, schedule_id, **kwargs):
        repo_id = kwargs.pop(OPTION_REPO_ID.keyword)
        return self.api.update_schedule(repo_id, TYPE_ID_IMPORTER_ISO, schedule_id, **kwargs)
