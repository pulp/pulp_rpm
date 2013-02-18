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
        _validate_num_threads,
        _validate_proxy_password,
        _validate_proxy_port,
        _validate_proxy_url,
        _validate_proxy_username,
        _validate_ssl_ca_cert,
        _validate_ssl_client_cert,
        _validate_ssl_client_key,
    )

    for v in validators:
        valid, error_message = v(config)
        if not valid:
            return valid, error_message

    return True, None


def _cast_to_int_without_allowing_floats(value):
    """
    Attempt to return an int of the value, without allowing any floating point values. This is useful to
    ensure that you get an int type out of value, while allowing a string representation of the value. If
    there are any non numerical characters in value, this will raise ValueError. 
    
    :param value: The value you want to validate
    :type  value: int or basestring
    :return:      The integer representation of value
    :rtype:       int
    """
    if isinstance(value, basestring):
        # We don't want to allow floating point values
        if not value.isdigit():
            raise ValueError()
        # Interpret num_threads as an integer
        value = int(value)
    if not isinstance(value, int):
        raise ValueError()
    return value


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


def _validate_num_threads(config):
    """
    Make sure the num_threads value is a positive integer.
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    num_threads = config.get(constants.CONFIG_NUM_THREADS)
    if num_threads is None:
        # We don't require num_threads to be set
        return True, None
    try:
        num_threads = _cast_to_int_without_allowing_floats(num_threads)
        if num_threads < 1:
            raise ValueError()
    except ValueError:
        error_message = _('The configuration parameter <%(num_threads_name)s> must be set to a positive '
                          'integer, but is currently set to <%(num_threads)s>.')%{
                            'num_threads_name': constants.CONFIG_NUM_THREADS, 'num_threads': num_threads}
        return False, error_message
    # No errors, so return success
    return True, None


def _validate_proxy_password(config):
    """
    Make sure the proxy_password is set if the proxy_user is set, and that it is a string.
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    proxy_password = config.get(constants.CONFIG_PROXY_PASSWORD)
    if proxy_password is None:
        # Proxy password is not required
        return True, None
    if not isinstance(proxy_password, basestring):
        return False, _('The configuration parameter <%(proxy_password_name)s> should be a string, but it '
                        'was %(type)s.')%{'proxy_password_name': constants.CONFIG_PROXY_PASSWORD,
                                          'type': type(proxy_password)}
    # If proxy_password is set, proxy_username must also be set
    if not config.get(constants.CONFIG_PROXY_USER):
        return False, _('The configuration parameter <%(password_name)s> requires the <%(username_name)s> '
                        'parameter to also be set.')%{'password_name': constants.CONFIG_PROXY_PASSWORD,
                                                      'username_name': constants.CONFIG_PROXY_USER}
    # We also require the URL to be set if the password is set
    if not config.get(constants.CONFIG_PROXY_URL):
        return False, _('The configuration parameter <%(password_name)s> requires the <%(url_name)s> '
                        'parameter to also be set.')%{'password_name': constants.CONFIG_PROXY_PASSWORD,
                                                      'url_name': constants.CONFIG_PROXY_URL}
    return True, None


def _validate_proxy_port(config):
    """
    Make sure the proxy_url is set if the proxy_port is set. Also, if it is set, make sure it is a positive
    integer.
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    proxy_port = config.get(constants.CONFIG_PROXY_PORT)
    if proxy_port is None:
        # Proxy port is not required
        return True, None
    if not config.get(constants.CONFIG_PROXY_URL):
        return False, _('The configuration parameter <%(name)s> requires the <%(url_name)s> '
                        'parameter to also be set.')%{'name': constants.CONFIG_PROXY_PORT,
                                                      'url_name': constants.CONFIG_PROXY_URL}
    try:
        proxy_port = _cast_to_int_without_allowing_floats(proxy_port)
        if proxy_port < 1:
            raise ValueError()
    except ValueError:
        error_message = _('The configuration parameter <%(name)s> must be set to a positive '
                          'integer, but is currently set to <%(value)s>.')%{
                            'name': constants.CONFIG_PROXY_PORT, 'value': proxy_port}
        return False, error_message
    # No errors, so return success
    return True, None


def _validate_proxy_url(config):
    """
    Make sure the proxy_url is a string, if it is set
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    proxy_url = config.get(constants.CONFIG_PROXY_URL)
    if proxy_url is None:
        # Proxy url is not required
        return True, None
    if not isinstance(proxy_url, basestring):
        return False, _('The configuration parameter <%(name)s> should be a string, but it '
                        'was %(type)s.')%{'name': constants.CONFIG_PROXY_URL,
                                          'type': type(proxy_url)}
    return True, None


def _validate_proxy_username(config):
    """
    Make sure the proxy_password is set if the proxy_user is set, and that the username is a string.
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    proxy_username = config.get(constants.CONFIG_PROXY_USER)
    if proxy_username is None:
        # Proxy username is not required
        return True, None
    if not isinstance(proxy_username, basestring):
        return False, _('The configuration parameter <%(name)s> should be a string, but it '
                        'was %(type)s.')%{'name': constants.CONFIG_PROXY_USER,
                                          'type': type(proxy_username)}
    # If proxy_password is set, proxy_username must also be set
    if not config.get(constants.CONFIG_PROXY_PASSWORD):
        return False, _('The configuration parameter <%(username_name)s> requires the <%(password_name)s> '
                        'parameter to also be set.')%{'password_name': constants.CONFIG_PROXY_PASSWORD,
                                                      'username_name': constants.CONFIG_PROXY_USER}
    # We also require the URL to be set if the password is set
    if not config.get(constants.CONFIG_PROXY_URL):
        return False, _('The configuration parameter <%(username_name)s> requires the <%(url_name)s> '
                        'parameter to also be set.')%{'username_name': constants.CONFIG_PROXY_USER,
                                                      'url_name': constants.CONFIG_PROXY_URL}
    return True, None


def _validate_ssl_ca_cert(config):
    """
    Make sure the ssl_ca_cert is a string, if it is set
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    ssl_ca_cert = config.get(constants.CONFIG_SSL_CA_CERT)
    if ssl_ca_cert is None:
        # ssl_ca_cert is not required
        return True, None
    if not isinstance(ssl_ca_cert, basestring):
        return False, _('The configuration parameter <%(name)s> should be a string, but it '
                        'was %(type)s.')%{'name': constants.CONFIG_SSL_CA_CERT,
                                          'type': type(ssl_ca_cert)}
    return True, None


def _validate_ssl_client_cert(config):
    """
    Make sure the ssl_client_cert is a string, if it is set
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    ssl_client_cert = config.get(constants.CONFIG_SSL_CLIENT_CERT)
    if ssl_client_cert is None:
        # ssl_client_cert is not required
        return True, None
    if not isinstance(ssl_client_cert, basestring):
        return False, _('The configuration parameter <%(name)s> should be a string, but it '
                        'was %(type)s.')%{'name': constants.CONFIG_SSL_CLIENT_CERT,
                                          'type': type(ssl_client_cert)}
    return True, None


def _validate_ssl_client_key(config):
    """
    Make sure the ssl_client_key is a string and that the cert is also provided, if the key is set.
    
    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :return:       Tuple of valid, error_message indicating success or failure as a boolean in the first, and
                   an error message in the second when the first is False
    :rtype:        tuple
    """
    ssl_client_key = config.get(constants.CONFIG_SSL_CLIENT_KEY)
    if ssl_client_key is None:
        # ssl_client_key is not required
        return True, None
    if not isinstance(ssl_client_key, basestring):
        return False, _('The configuration parameter <%(name)s> should be a string, but it '
                        'was %(type)s.')%{'name': constants.CONFIG_SSL_CLIENT_KEY,
                                          'type': type(ssl_client_key)}
    # If the key is set, we should also have a cert
    if not config.get(constants.CONFIG_SSL_CLIENT_CERT):
        return False, _('The configuration parameter <%(key_name)s> requires the <%(cert_name)s> '
                        'parameter to also be set.')%{'key_name': constants.CONFIG_SSL_CLIENT_KEY,
                                                      'cert_name': constants.CONFIG_SSL_CLIENT_CERT}
    return True, None