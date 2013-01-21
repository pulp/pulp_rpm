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
from gettext import gettext as _
import logging

from pulp_rpm.common import constants

logger = logging.getLogger(__name__)


def validate(config):
    """
    Validates the configuration for an ISO importer.

    :param config: configuration to validate
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return:       A tuple, first element a bool indicating success, second a string of any error
                   messages
    :rtype:        tuple
    """
    validators = (
        # TODO: Don't worry about validating feed_url, or maybe a quick regex or something.
        _validate_feed_url,
        _validate_max_speed,
    )

    for v in validators:
        valid, error_message = v(config)
        if not valid:
            return valid, error_message

    return True, None


# TODO: Should we validate that the URL is a valid URL? Currently we only validate that it is set to
#       something that evaluates to True.
def _validate_feed_url(config):
    """
    Make sure the feed_url is set.

    :rtype: tuple
    """
    feed_url = config.get(constants.CONFIG_FEED_URL)
    # TODO: feed_urls are not required. So don't require them.
    if not feed_url:
        return False, _('<%(feed_url)s> is a required configuration parameter.')%{
            'feed_url': constants.CONFIG_FEED_URL}
    return True, None


def _validate_max_speed(config):
    """
    Make sure the max speed can be cast to a number, if it is defined.

    :rtype: tuple
    """
    max_speed = config.get(constants.CONFIG_MAX_SPEED)
    # max_speed is not required
    if max_speed is None:
        return True, None
    try:
        max_speed = float(max_speed)
    except ValueError:
        return False, _('The configuration parameter <%(max_speed)s> must be set to a numerical value, but is currently set to <%(max_speed)s>.')
