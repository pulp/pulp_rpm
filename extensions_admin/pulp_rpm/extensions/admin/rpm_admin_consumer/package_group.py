"""
Contains package (RPM) group management section and commands.
"""

from gettext import gettext as _

from okaara.prompt import COLOR_RED

from pulp.client.commands.consumer import content as consumer_content
from pulp.client.extensions.extensions import PulpCliSection

from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP
from pulp_rpm.extensions.admin.content_schedules import YumConsumerContentCreateScheduleCommand

# progress tracker -------------------------------------------------------------


class YumConsumerPackageProgressTracker(consumer_content.ConsumerContentProgressTracker):
    def display_details(self, details):
        action = details.get('action')
        package = details.get('package')
        error = details.get('error')
        self.details = None
        if action:
            self.details = '%+12s: %s' % (action, package)
            self.prompt.write(self.details)
            return
        if error:
            action = 'Error'
            self.details = '%+12s: %s' % (action, error)
            self.prompt.write(self.details, COLOR_RED)
            return


# sections ---------------------------------------------------------------------

class YumConsumerPackageGroupSchedulesSection(PulpCliSection):
    def __init__(self, context, action):
        description = _('manage consumer package group %s schedules' % action)
        super(YumConsumerPackageGroupSchedulesSection, self).__init__('schedules', description)

        self.add_command(consumer_content.ConsumerContentListScheduleCommand(context, action))
        self.add_command(
            YumConsumerContentCreateScheduleCommand(context, action, TYPE_ID_PKG_GROUP))
        self.add_command(consumer_content.ConsumerContentDeleteScheduleCommand(context, action))
        self.add_command(consumer_content.ConsumerContentUpdateScheduleCommand(context, action))
        self.add_command(consumer_content.NextRunCommand(context, action))
