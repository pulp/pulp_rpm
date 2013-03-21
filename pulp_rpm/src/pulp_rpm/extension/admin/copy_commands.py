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

from pulp.client.commands.unit import UnitCopyCommand
from pulp.client.extensions.extensions import PulpCliFlag
from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO,
                                 TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY)

# -- constants ----------------------------------------------------------------

DESC_RPM = _('copy RPMs from one repository to another')
DESC_SRPM = _('copy SRPMs from one repository to another')
DESC_DRPM = _('copy DRPMs from one repository to another')
DESC_ERRATA = _('copy errata from one repository to another')
DESC_DISTRIBUTION = _('copy distributions from one repository to another')
DESC_PKG_GROUP = _('copy package groups from one repository to another')
DESC_PKG_CATEGORY = _('copy package categories from one repository to another')

DESC_RECURSIVE = _('if specified, any dependencies of units being copied will be copied as well')
FLAG_RECURSIVE = PulpCliFlag('--recursive', DESC_RECURSIVE)

# -- commands -----------------------------------------------------------------

class RecursiveCopyCommand(UnitCopyCommand):
    """
    Base class for all copy commands in this module that should support specifying a recursive
    option to the plugin.

    In 2.0, all of these copy commands supported the ability to indicate the copy should be
    recursive. I'm not entirely sure the plugin supports it in all cases, but for now I'm going to
    stick with the approach that it's supported for all of them.
    """

    def __init__(self, context, name, description, type_id):
        super(RecursiveCopyCommand, self).__init__(context, name=name, description=description, type_id=type_id)

        self.add_flag(FLAG_RECURSIVE)

    def generate_override_config(self, **kwargs):
        override_config = {}

        if kwargs[FLAG_RECURSIVE.keyword]:
            override_config['recursive'] = True

        return override_config


class RpmCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(RpmCopyCommand, self).__init__(context, 'rpm', DESC_RPM, TYPE_ID_RPM)


class SrpmCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(SrpmCopyCommand, self).__init__(context, 'srpm', DESC_SRPM, TYPE_ID_SRPM)


class DrpmCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(DrpmCopyCommand, self).__init__(context, 'drpm', DESC_DRPM, TYPE_ID_DRPM)


class ErrataCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(ErrataCopyCommand, self).__init__(context, 'errata', DESC_ERRATA, TYPE_ID_ERRATA)


class DistributionCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(DistributionCopyCommand, self).__init__(context, 'distribution', DESC_DISTRIBUTION,
                                                      TYPE_ID_DISTRO)


class PackageGroupCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(PackageGroupCopyCommand, self).__init__(context, 'group', DESC_PKG_GROUP, TYPE_ID_PKG_GROUP)


class PackageCategoryCopyCommand(RecursiveCopyCommand):

    def __init__(self, context):
        super(PackageCategoryCopyCommand, self).__init__(context, 'category', DESC_PKG_CATEGORY,
                                                         TYPE_ID_PKG_CATEGORY)
