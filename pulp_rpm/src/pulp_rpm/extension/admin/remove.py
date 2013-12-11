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

from pulp.client.commands.unit import UnitRemoveCommand

from pulp_rpm.common.constants import DISPLAY_UNITS_THRESHOLD
from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM,
                                 TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_ENVIRONMENT,
                                 TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO, UNIT_KEY_RPM)
from pulp_rpm.extension import criteria_utils
from pulp_rpm.extension.admin import units_display

# -- constants ----------------------------------------------------------------

DESC_RPM = _('remove RPMs from a repository')
DESC_SRPM = _('remove SRPMs from a repository')
DESC_DRPM = _('remove DRPMs from a repository')
DESC_ERRATA = _('remove errata from a repository')
DESC_GROUP = _('remove package groups from a repository')
DESC_CATEGORY = _('remove package categories from a repository')
DESC_ENVIRONMENT = _('remove package environments from a repository')
DESC_DISTRIBUTION = _('remove distributions from a repository')

# -- commands -----------------------------------------------------------------


class BaseRemoveCommand(UnitRemoveCommand):

    def __init__(self, context, name, description, type_id, unit_threshold=DISPLAY_UNITS_THRESHOLD):
        UnitRemoveCommand.__init__(self, context, name=name, description=description,
                                   type_id=type_id)
        self.unit_threshold = unit_threshold

    def succeeded(self, task):
        removed_units = task.result  # entries are a dict containing unit_key and type_id
        units_display.display_units(self.prompt, removed_units, self.unit_threshold)


class PackageRemoveCommand(BaseRemoveCommand):
    """
    Used for only RPMs and SRPMs to intercept the criteria and use sort indexes when necessary.
    """
    @staticmethod
    def _parse_key_value(args):
        return criteria_utils.parse_key_value(args)

    @classmethod
    def _parse_sort(cls, sort_args):
        return criteria_utils.parse_sort(BaseRemoveCommand, sort_args)

    def modify_user_input(self, user_input):
        super(PackageRemoveCommand, self).modify_user_input(user_input)

        # Work around to scope the fields loaded by the platform to limit the amount of
        # RAM used. This addition will find its way to the criteria parsing in the bindings.
        user_input['fields'] = UNIT_KEY_RPM


class RpmRemoveCommand(PackageRemoveCommand):

    def __init__(self, context):
        super(RpmRemoveCommand, self).__init__(context, 'rpm', DESC_RPM, TYPE_ID_RPM)


class SrpmRemoveCommand(PackageRemoveCommand):

    def __init__(self, context):
        super(SrpmRemoveCommand, self).__init__(context, 'srpm', DESC_SRPM, TYPE_ID_SRPM)


class DrpmRemoveCommand(BaseRemoveCommand):

    def __init__(self, context):
        super(DrpmRemoveCommand, self).__init__(context, 'drpm', DESC_DRPM, TYPE_ID_DRPM)


class ErrataRemoveCommand(BaseRemoveCommand):

    def __init__(self, context):
        super(ErrataRemoveCommand, self).__init__(context, 'errata', DESC_ERRATA, TYPE_ID_ERRATA)


class PackageGroupRemoveCommand(BaseRemoveCommand):

    def __init__(self, context):
        super(PackageGroupRemoveCommand, self).__init__(context, 'group', DESC_GROUP,
                                                        TYPE_ID_PKG_GROUP)


class PackageCategoryRemoveCommand(BaseRemoveCommand):

    def __init__(self, context):
        super(PackageCategoryRemoveCommand, self).__init__(context, 'category', DESC_CATEGORY,
                                                           TYPE_ID_PKG_CATEGORY)


class PackageEnvironmentRemoveCommand(BaseRemoveCommand):

    def __init__(self, context):
        super(PackageEnvironmentRemoveCommand, self).__init__(context, 'environment',
                                                              DESC_ENVIRONMENT,
                                                              TYPE_ID_PKG_ENVIRONMENT)


class DistributionRemoveCommand(BaseRemoveCommand):

    def __init__(self, context):
        super(DistributionRemoveCommand, self).__init__(context, 'distribution', DESC_DISTRIBUTION,
                                                        TYPE_ID_DISTRO)
