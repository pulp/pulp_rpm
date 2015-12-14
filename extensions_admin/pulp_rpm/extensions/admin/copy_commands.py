from gettext import gettext as _

from pulp.client.commands.unit import UnitCopyCommand
from pulp.client.extensions.extensions import PulpCliFlag

from pulp_rpm.extensions.admin import units_display, criteria_utils
from pulp_rpm.common.constants import DISPLAY_UNITS_THRESHOLD, CONFIG_RECURSIVE
from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_PKG_ENVIRONMENT, TYPE_ID_YUM_REPO_METADATA_FILE,
                                 UNIT_KEY_RPM)


# -- constants ----------------------------------------------------------------

DESC_RPM = _('copy RPMs from one repository to another')
DESC_SRPM = _('copy SRPMs from one repository to another')
DESC_DRPM = _('copy DRPMs from one repository to another')
DESC_ERRATA = _('copy errata from one repository to another')
DESC_DISTRIBUTION = _('copy distributions from one repository to another')
DESC_PKG_GROUP = _('copy package groups from one repository to another')
DESC_PKG_CATEGORY = _('copy package categories from one repository to another')
DESC_PKG_ENVIRONMENT = _('copy package environment from one repository to another')
DESC_METAFILE = _('copy yum repo metadata files from one repository to another')
DESC_ALL = _('copy all content units from one repository to another')

DESC_RECURSIVE = _(
    'if specified, any dependencies of units being copied that are in the source repo '
    'will be copied as well')
FLAG_RECURSIVE = PulpCliFlag('--recursive', DESC_RECURSIVE)

# -- commands -----------------------------------------------------------------


class NonRecursiveCopyCommand(UnitCopyCommand):
    """
    Base class for all copy commands in this module that need not support specifying a recursive
    option to the plugin.
    """

    def __init__(self, context, name, description, type_id, unit_threshold=DISPLAY_UNITS_THRESHOLD):
        super(NonRecursiveCopyCommand, self).__init__(context, name=name, description=description,
                                                      type_id=type_id)

        self.unit_threshold = unit_threshold

    def get_formatter_for_type(self, type_id):
        """
        Hook to get a the formatter for a given type

        :param type_id: the type id for which we need to get the formatter
        :type type_id: str
        """
        return units_display.get_formatter_for_type(type_id)


class RecursiveCopyCommand(NonRecursiveCopyCommand):
    """
    Base class for all copy commands in this module that should support specifying a recursive
    option to the plugin.
    """

    def __init__(self, context, name, description, type_id, unit_threshold=DISPLAY_UNITS_THRESHOLD):
        super(RecursiveCopyCommand, self).__init__(context, name=name, description=description,
                                                   type_id=type_id)

        self.add_flag(FLAG_RECURSIVE)

    def generate_override_config(self, **kwargs):
        override_config = {}

        if kwargs[FLAG_RECURSIVE.keyword]:
            override_config[CONFIG_RECURSIVE] = True

        return override_config


class PackageCopyCommand(RecursiveCopyCommand):
    """
    Used for only RPMs and SRPMs to intercept the criteria and use sort indexes when necessary.
    """

    @staticmethod
    def _parse_key_value(args):
        return criteria_utils.parse_key_value(args)

    @classmethod
    def _parse_sort(cls, sort_args):
        return criteria_utils.parse_sort(RecursiveCopyCommand, sort_args)

    def modify_user_input(self, user_input):
        super(PackageCopyCommand, self).modify_user_input(user_input)

        # Work around to scope the fields loaded by the platform to limit the amount of
        # RAM used. This addition will find its way to the criteria parsing in the bindings.
        user_input['fields'] = UNIT_KEY_RPM


class RpmCopyCommand(PackageCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'rpm', DESC_RPM, TYPE_ID_RPM)


class SrpmCopyCommand(PackageCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'srpm', DESC_SRPM, TYPE_ID_SRPM)


class DrpmCopyCommand(RecursiveCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'drpm', DESC_DRPM, TYPE_ID_DRPM)


class ErrataCopyCommand(RecursiveCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'errata', DESC_ERRATA, TYPE_ID_ERRATA)


class DistributionCopyCommand(NonRecursiveCopyCommand):
    def __init__(self, context):
        NonRecursiveCopyCommand.__init__(self, context, 'distribution', DESC_DISTRIBUTION,
                                         TYPE_ID_DISTRO)


class PackageGroupCopyCommand(RecursiveCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'group', DESC_PKG_GROUP, TYPE_ID_PKG_GROUP)


class PackageCategoryCopyCommand(RecursiveCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'category', DESC_PKG_CATEGORY,
                                      TYPE_ID_PKG_CATEGORY)


class PackageEnvironmentCopyCommand(RecursiveCopyCommand):
    def __init__(self, context):
        RecursiveCopyCommand.__init__(self, context, 'environment', DESC_PKG_ENVIRONMENT,
                                      TYPE_ID_PKG_ENVIRONMENT)


class YumRepoMetadataFileCommand(NonRecursiveCopyCommand):
    def __init__(self, context):
        NonRecursiveCopyCommand.__init__(self, context, 'metafile', DESC_METAFILE,
                                         TYPE_ID_YUM_REPO_METADATA_FILE)

class AllCopyCommand(NonRecursiveCopyCommand):
    def __init__(self, context):
        NonRecursiveCopyCommand.__init__(self, context, 'all', DESC_ALL, None)
