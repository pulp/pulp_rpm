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

import os


def relative_path_to_data_dir():
    """
    Determine the relative path the server data directory.
    :return: relative path to the data directory.
    :rtype: str
    :raise RuntimeError: when the path cannot be determined.
    """
    potential_data_dir = 'pulp_rpm/pulp_rpm/test/unit/server/data/'

    while potential_data_dir:

        if os.path.exists(potential_data_dir):
            return potential_data_dir

        potential_data_dir = potential_data_dir.split('/', 1)[1]

    raise RuntimeError('Cannot determine data directory')


def full_path_to_data_dir():
    """
    Determine the full path the server data directory.
    :return: full path to the data directory.
    :rtype: str
    :raise RuntimeError: when the path cannot be determined.
    """
    current_dir = os.getcwd()
    relative_path = relative_path_to_data_dir()
    return os.path.join(current_dir, relative_path)
