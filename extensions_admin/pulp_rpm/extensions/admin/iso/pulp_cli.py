from pulp.client.extensions.decorator import priority

from pulp_rpm.extensions.admin.iso.structure import add_iso_section


@priority()
def initialize(context):
    """
    :param context: The client context that we can use to interact with the client framework
    :type  context: pulp.client.extensions.core.ClientContext
    """
    add_iso_section(context)
