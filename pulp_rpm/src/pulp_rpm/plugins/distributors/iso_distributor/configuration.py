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
from pulp_rpm.yum_plugin import util as yum_utils


logger = logging.getLogger(__name__)


def validate(config):
    """
    Validate a distributor configuration for an ISO distributor.

    :param config: the config to be validated
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       tuple of (is_valid, error_message)
    :rtype:        tuple
    """
    # This is a tuple of tuples. The inner tuples have two elements. The first element is a validation method
    # that should be run, and the second element is the name of the config setting that should be validated by
    # it.
    validations = (
        (_validate_required_bool, constants.CONFIG_SERVE_HTTP,),
        (_validate_required_bool, constants.CONFIG_SERVE_HTTPS,),
        (_validate_ssl_cert, constants.CONFIG_SSL_AUTH_CA_CERT),
    )

    for validation in validations:
        result, msg = validation[0](config, validation[1])
        if not result:
            return result, msg

    return True, None


def _validate_ssl_cert(config, setting_name):
    """
    Ensure that the setting_name from config is a valid SSL certificate, if it is given. This setting is not
    required.

    :param config:       The config to validate
    :type  config:       pulp.plugins.config.PluginCallConfiguration
    :param setting_name: The name of the setting that needs to be validated
    :type  setting_name: str
    :return:             A tuple of (valid, message)
    :rtype:              tuple
    """
    ssl_cert = config.get(setting_name)
    if not ssl_cert:
        # The cert is not required
        return True, None
    if not yum_utils.validate_cert(ssl_cert):
        msg = _("The SSL certificate <%(s)s> is not a valid certificate.")
        msg = msg % {'s': setting_name}
        return False, msg
    return True, None


def _validate_required_bool(config, bool_setting):
    """
    Make sure the given bool_setting is set and is a bool.

    :param config:       The config to validate
    :type  config:       pulp.plugins.config.PluginCallConfiguration
    :param bool_setting: The name of the setting that needs to be validated
    :type  bool_setting: str
    :return:             A tuple of (valid, message)
    :rtype:              tuple
    """
    value = config.get_boolean(bool_setting)
    if value is None:
        return False, _('The value for <%(k)s> must be either "true" or "false"')%{
                        'k': bool_setting}
    # No errors, so return True
    return True, None
