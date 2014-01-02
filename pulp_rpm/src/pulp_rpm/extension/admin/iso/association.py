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

from pulp.client.commands.unit import UnitRemoveCommand, UnitCopyCommand

from pulp_rpm.common.ids import TYPE_ID_ISO


def _get_formatter(type_id):
    """
    Return a method that can be used to provide a formatted name for an ISO unit
    """
    if type_id != TYPE_ID_ISO:
            raise ValueError(_("The iso module formatter can not process %s units.") % type_id)
    return lambda x: "%(name)s" % x


class IsoRemoveCommand(UnitRemoveCommand):
    """
    CLI Command for removing an iso unit from a repository
    """
    def __init__(self, context):
        UnitRemoveCommand.__init__(self, context, type_id=TYPE_ID_ISO)

    def get_formatter_for_type(self, type_id):
        """
        Hook to get a the formatter for a given type

        :param type_id: the type id for which we need to get the formatter
        :type type_id: str
        :returns: a function to provide a user readable formatted name for a type
        :rtype: function
        """
        return _get_formatter(type_id)


class IsoCopyCommand(UnitCopyCommand):
    """
    CLI Command for copying an iso unit from one repo to another
    """
    def __init__(self, context):
        UnitCopyCommand.__init__(self, context, type_id=TYPE_ID_ISO)

    def get_formatter_for_type(self, type_id):
        """
        Hook to get a the formatter for a given type

        :param type_id: the type id for which we need to get the formatter
        :type type_id: str
        :returns: a function to provide a user readable formatted name for a type
        :rtype: function
        """
        return _get_formatter(type_id)
