from gettext import gettext as _

from pulp.client.commands.consumer.content import (
    ConsumerContentCreateScheduleCommand, ConsumerContentScheduleStrategy,
    OPTION_CONTENT_TYPE_ID, OPTION_CONTENT_UNIT)
from pulp.client.commands.options import OPTION_CONSUMER_ID
from pulp.client.extensions.extensions import PulpCliOption

from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP

# -- commands -----------------------------------------------------------------

class YumConsumerContentCreateScheduleCommand(ConsumerContentCreateScheduleCommand):
    def __init__(self, context, action, content_type, strategy=None):
        assert(content_type in (TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP))

        strategy = strategy or YumConsumerContentScheduleStrategy(context, action, content_type)
        super(YumConsumerContentCreateScheduleCommand, self).__init__(context, action, strategy)

        # This will be substituted by the options below
        self.options.remove(OPTION_CONTENT_TYPE_ID)
        self.options.remove(OPTION_CONTENT_UNIT)

        if content_type == TYPE_ID_RPM:
            self.add_option(PulpCliOption('--name', _('package name; may be repeated for multiple packages'),
                                          required=True, allow_multiple=True, aliases=['-n']))
        elif content_type == TYPE_ID_ERRATA:
            self.add_option(PulpCliOption('--errata-id', _('erratum id; may be repeated for multiple errata'),
                                          required=True, allow_multiple=True, aliases=['-e']))
        elif content_type == TYPE_ID_PKG_GROUP:
            self.add_option(PulpCliOption('--name', _('package group name; may be repeated for multiple package groups'),
                                          required=True, allow_multiple=True, aliases=['-n']))


# -- framework classes --------------------------------------------------------

class YumConsumerContentScheduleStrategy(ConsumerContentScheduleStrategy):

    # See super class for method documentation

    def __init__(self, context, action, content_type):
        assert content_type in (TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP)

        super(YumConsumerContentScheduleStrategy, self).__init__(context, action)

        self.content_type = content_type

    def create_schedule(self, schedule, failure_threshold, enabled, kwargs):
        consumer_id = kwargs[OPTION_CONSUMER_ID.keyword]
        units = []
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

