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
import logging

from pulp_rpm.common import constants

logger = logging.getLogger(__name__)


# TODO: Make sure feed_url is a string, not unicode
CONFIG_DEFAULTS = {constants.CONFIG_NUM_THREADS: 5}
# This is used when we try to validate these values, to ensure they can all be cast to expected
# types.
CONFIG_TYPES = {constants.CONFIG_FEED_URL: str, constants.CONFIG_NUM_THREADS: int,
                constants.CONFIG_SSL_CA_CERT: str, constants.CONFIG_SSL_CLIENT_CERT: str,
                constants.CONFIG_PROXY_URL: str, constants.CONFIG_PROXY_PORT: int,
                constants.CONFIG_PROXY_USER: str, constants.CONFIG_PROXY_PASSWORD: str,
                constants.CONFIG_MAX_SPEED: float, constants.CONFIG_SERVE_HTTP: bool,
                constants.CONFIG_SERVE_HTTPS: bool, constants.CONFIG_HTTP_DIR: str,
                constants.CONFIG_HTTPS_DIR: str}


def validate(config):
    """
    Validates the configuration for an ISO importer.

    :param config: configuration to validate
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return:       A tuple, first element a bool indicating success, second a string of any error
                   messages
    :rtype:        tuple
    """
    # Set the config defaults
    config.default_config = CONFIG_DEFAULTS

    for config_key, config_type in enumerate(CONFIG_TYPES):
        current_value = config.get(config_key)
        # if current_value is not None and not isinstance(current_value, CONFIG_TYPES[config_key]):
    return True, None
