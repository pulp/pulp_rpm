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
    UpdateScheduleCommand, NextRunCommand, RepoScheduleStrategy)
from pulp.client.commands.options import OPTION_REPO_ID
from pulp_rpm.common.ids import YUM_IMPORTER_ID

# -- constants ----------------------------------------------------------------

DESC_LIST = _('list scheduled sync operations')
DESC_CREATE = _('adds a new scheduled sync operation')
DESC_DELETE = _('delete a sync schedule')
DESC_UPDATE = _('updates an existing schedule')
DESC_NEXT_RUN = _('displays the next scheduled sync run for a repository')

# -- commands -----------------------------------------------------------------

class RpmListScheduleCommand(ListScheduleCommand):
    def __init__(self, context):
        strategy = RepoScheduleStrategy(context.server.repo_sync_schedules, YUM_IMPORTER_ID)
        super(RpmListScheduleCommand, self).__init__(context, strategy,
                                                     description=DESC_LIST)
        self.add_option(OPTION_REPO_ID)


class RpmCreateScheduleCommand(CreateScheduleCommand):
    def __init__(self, context):
        strategy = RepoScheduleStrategy(context.server.repo_sync_schedules, YUM_IMPORTER_ID)
        super(RpmCreateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_CREATE)
        self.add_option(OPTION_REPO_ID)


class RpmDeleteScheduleCommand(DeleteScheduleCommand):
    def __init__(self, context):
        strategy = RepoScheduleStrategy(context.server.repo_sync_schedules, YUM_IMPORTER_ID)
        super(RpmDeleteScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_DELETE)
        self.add_option(OPTION_REPO_ID)


class RpmUpdateScheduleCommand(UpdateScheduleCommand):
    def __init__(self, context):
        strategy = RepoScheduleStrategy(context.server.repo_sync_schedules, YUM_IMPORTER_ID)
        super(RpmUpdateScheduleCommand, self).__init__(context, strategy,
                                                       description=DESC_UPDATE)
        self.add_option(OPTION_REPO_ID)


class RpmNextRunCommand(NextRunCommand):
    def __init__(self, context):
        strategy = RepoScheduleStrategy(context.server.repo_sync_schedules, YUM_IMPORTER_ID)
        super(RpmNextRunCommand, self).__init__(context, strategy,
                                                description=DESC_NEXT_RUN)
        self.add_option(OPTION_REPO_ID)
