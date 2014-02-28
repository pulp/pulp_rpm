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

from pulp.client.extensions.decorator import priority

from pulp_rpm.extensions.admin.iso.structure import add_iso_section


@priority()
def initialize(context):
    """
    :param context: The client context that we can use to interact with the client framework
    :type  context: pulp.client.extensions.core.ClientContext
    """
    add_iso_section(context)
