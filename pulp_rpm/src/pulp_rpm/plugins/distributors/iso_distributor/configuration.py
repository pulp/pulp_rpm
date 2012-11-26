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
    Validate a distributor configuration for an ISO distributor.

    :param config: the config to be validated
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       tuple of (is_valid, error_message)
    :rtype:        tuple
    """
    logger.debug(config.keys())
    validate_args = (
        (constants.CONFIG_SERVE_HTTP, constants.CONFIG_HTTP_DIR),
        (constants.CONFIG_SERVE_HTTPS, constants.CONFIG_HTTPS_DIR),
    )

    for args in validate_args:
        result, msg = _validate(config, *args)
        if not result:
            return result, msg

    return True, None


def _validate(config, serve_setting, publish_dir_setting):
    """
    Make sure the serve and dir settings are sane for HTTP.

    :return: A tuple of (valid, message)
    :rtype:  tuple
    """
    serve = config.get_boolean(serve_setting)
    if serve is None:
        return False, _('The value for <%(k)s> must be either "true" or "false"')%{
                        'k': serve_setting}
    # TODO: Figure out the details of how to get this setting in a conf file so the user doesn't
    #       have to specify it. Then uncomment the next block.
    # If serve is set, we should check that the directory to publish at is also set
    # if serve:
    #     publish_dir = config.get(publish_dir_setting)
    #     if not publish_dir:
    #         return False, _('The value for <%(h)s> must be set when <%(k)s> is true.')%{
    #                         'h': publish_dir_setting, 'k': serve_setting}
    # No errors, so return True
    return True, None
