# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

"""
We no longer need the hard link to the yum distributor.  This migration removes the symlink
so that the entry point version will take priority.
"""

import os

DISTRIBUTOR_LIB_DIRECTORY = '/usr/lib/pulp/plugins/distributors/yum_distributor'


def migrate():
    """
    remove the link to the yum_distributor lib directory
    """
    if os.path.exists(DISTRIBUTOR_LIB_DIRECTORY):
        os.unlink(DISTRIBUTOR_LIB_DIRECTORY)
