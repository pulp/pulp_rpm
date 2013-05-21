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

import logging

from pulp.common.plugins import importer_constants

from pulp_rpm.common import constants

_LOGGER = logging.getLogger(__name__)


class Config(object):
    def __init__(self, platform_config):
        self.feed = platform_config.get(importer_constants.KEY_FEED)
        self.newest = platform_config.get_boolean(constants.CONFIG_NEWEST) or False
