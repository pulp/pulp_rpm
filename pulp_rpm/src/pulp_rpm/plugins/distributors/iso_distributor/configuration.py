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
        (constants.CONFIG_SERVE_HTTP,),
        (constants.CONFIG_SERVE_HTTPS,),
    )

    for args in validate_args:
        result, msg = _validate(config, *args)
        if not result:
            return result, msg

    return True, None


def _validate(config, serve_setting):
    """
    Make sure the serve and dir settings are sane for HTTP.

    :return: A tuple of (valid, message)
    :rtype:  tuple
    """
    serve = config.get_boolean(serve_setting)
    if serve is None:
        return False, _('The value for <%(k)s> must be either "true" or "false"')%{
                        'k': serve_setting}
    # No errors, so return True
    return True, None
