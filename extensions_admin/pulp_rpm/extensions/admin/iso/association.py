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
