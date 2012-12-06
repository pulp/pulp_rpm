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

from pulp.client.commands.unit import UnitRemoveCommand

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM,
                                 TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
                                 TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO)

# -- constants ----------------------------------------------------------------

DESC_RPM = _('remove RPMs from a repository')
DESC_SRPM = _('remove SRPMs from a repository')
DESC_DRPM = _('remove DRPMs from a repository')
DESC_ERRATA = _('remove errata from a repository')
DESC_GROUP = _('remove package groups from a repository')
DESC_CATEGORY = _('remove package categories from a repository')
DESC_DISTRIBUTION = _('remove distributions from a repository')

# -- commands -----------------------------------------------------------------

class RpmRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(RpmRemoveCommand, self).__init__(
                context, name='rpm', description=DESC_RPM, type_id=TYPE_ID_RPM)


class SrpmRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(SrpmRemoveCommand, self).__init__(
                context, name='srpm', description=DESC_SRPM, type_id=TYPE_ID_SRPM)


class DrpmRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(DrpmRemoveCommand, self).__init__(
                context, name='drpm', description=DESC_DRPM, type_id=TYPE_ID_DRPM)


class ErrataRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(ErrataRemoveCommand, self).__init__(
                context, name='errata', description=DESC_ERRATA, type_id=TYPE_ID_ERRATA)


class PackageGroupRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(PackageGroupRemoveCommand, self).__init__(
                context, name='group', description=DESC_GROUP, type_id=TYPE_ID_PKG_GROUP)


class PackageCategoryRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(PackageCategoryRemoveCommand, self).__init__(context, 'category',
                                                           DESC_CATEGORY, TYPE_ID_PKG_CATEGORY)

class DistributionRemoveCommand(UnitRemoveCommand):

    def __init__(self, context):
        super(DistributionRemoveCommand, self).__init__(context, 'distribution',
                                                           DESC_DISTRIBUTION, TYPE_ID_DISTRO)
