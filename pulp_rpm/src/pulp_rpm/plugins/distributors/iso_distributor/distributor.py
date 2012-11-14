# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version 
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
from pulp.plugins.distributor import Distributor

from pulp_rpm.common import ids
from pulp_rpm.plugins.distributors.iso_distributor import configuration


def entry_point():
    """
    Advertise the ISODistributor to Pulp.

    :return: ISODistributor and its empty config
    :rtype:  tuple
    """
    return ISODistributor, {}


class ISODistributor(Distributor):
    """
    Distribute ISOs like a boss.
    """
    @classmethod
    def metadata(cls):
        """
        Advertise the capabilities of the mighty ISODistributor.
        
        :return: The description of the impressive ISODistributor's capabilities.
        :rtype:  dict
        """
        return {
            'id': ids.TYPE_ID_DISTRIBUTOR_ISO,
            'display_name': 'ISO Distributor',
            'types': [ids.TYPE_ID_ISO]
        }

    def validate_config(self, repo, config, related_repos):
        return configuration.validate(config)
