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
        _validate_feed_url,
        _validate_max_speed,
        _validate_validate_downloads,
    )

    for v in validators:
        valid, error_message = v(config)
        if not valid:
            return valid, error_message

    return True, None


def _validate_feed_url(config):
    """
    Make sure the feed_url is set.

    :rtype: tuple
    """
    feed_url = config.get(constants.CONFIG_FEED_URL)
    # feed_urls are not required.
    if not feed_url:
        return True, None
    if not isinstance(feed_url, basestring):
        return False, _('<%(feed_url)s> must be a string.')%{'feed_url': constants.CONFIG_FEED_URL}
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
        if max_speed <= 0:
            raise ValueError()
    except ValueError:
        return False, _('The configuration parameter <%(max_speed_name)s> must be set to a positive '
                        'numerical value, but is currently set to <%(max_speed_value)s>.')%{
                            'max_speed_name': constants.CONFIG_MAX_SPEED, 'max_speed_value': max_speed}
    return True, None


def _validate_validate_downloads(config):
    """
    This (humorously named) method will validate the optional config option called "validate_downloads". If it
    is set, it must be a boolean, otherwise it may be None.
    
    :param config: the config to be validated
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       tuple of (is_valid, error_message)
    :rtype:        tuple
    """
    validate_downloads = config.get(constants.CONFIG_VALIDATE_DOWNLOADS)
    if validate_downloads is None:
        # validate_downloads is not a required parameter
        return True, None
    if isinstance(validate_downloads, basestring):
        validate_downloads = config.get_boolean(constants.CONFIG_VALIDATE_DOWNLOADS)
    if isinstance(validate_downloads, bool):
        return True, None
    return False, _('The configuration parameter <%(name)s> must be set to a boolean value, but is currently '
                    'set to <%(value)s>.')%{'name': constants.CONFIG_VALIDATE_DOWNLOADS,
                                            'value': validate_downloads}