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


logger = logging.getLogger(__name__)


# TODO: Make sure feed_url is a string, not unicode
CONFIG_DEFAULTS = {'num_threads': 5}
CONFIG_TYPES = {'feed_url': str, 'num_threads': int, 'ssl_ca_cert': str,
                'ssl_client_cert': str, 'proxy_url': str,
                'proxy_port': int, 'proxy_user': str,
                'proxy_password': str, 'max_speed': float}


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
