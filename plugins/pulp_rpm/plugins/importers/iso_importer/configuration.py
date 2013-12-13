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

from pulp.common.plugins import importer_constants

from pulp_rpm.plugins import configuration_utils

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
        _validate_remove_missing_units,
        _validate_ssl_ca_cert,
        _validate_ssl_client_cert,
        _validate_ssl_client_key,
        _validate_validate_downloads,
    )

    for v in validators:
        try:
            v(config)
        except configuration_utils.ValidationError, e:
            return False, str(e)

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
    Make sure the feed_url is a string, if it is set.
    """
    feed_url = config.get(importer_constants.KEY_FEED)
    # feed_urls are not required if all of the other feed related settings are None
    dependencies = [
        importer_constants.KEY_MAX_SPEED, importer_constants.KEY_MAX_DOWNLOADS,
        importer_constants.KEY_PROXY_PASS, importer_constants.KEY_PROXY_PORT,
        importer_constants.KEY_PROXY_HOST, importer_constants.KEY_PROXY_USER,
        importer_constants.KEY_UNITS_REMOVE_MISSING, importer_constants.KEY_SSL_CA_CERT,
        importer_constants.KEY_SSL_CLIENT_CERT, importer_constants.KEY_SSL_CLIENT_KEY,
        importer_constants.KEY_VALIDATE]
    if not feed_url and all([config.get(setting) is None for setting in dependencies]):
        return
    elif not feed_url:
        msg = _('The configuration parameter <%(name)s> is required when any of the following other '
                'parameters are defined: ' + ', '.join(dependencies) + '.')
        msg = msg % {'name': importer_constants.KEY_FEED}
        raise configuration_utils.ValidationError(msg)

    if not isinstance(feed_url, basestring):
        msg = _('<%(feed_url)s> must be a string.')
        msg = msg % {'feed_url': importer_constants.KEY_FEED}
        raise configuration_utils.ValidationError(msg)


def _validate_max_speed(config):
    """
    Make sure the max speed can be cast to a number, if it is defined.

    :rtype: tuple
    """
    max_speed = config.get(importer_constants.KEY_MAX_SPEED)
    # max_speed is not required
    if max_speed is None:
        return

    try:
        max_speed = float(max_speed)
        if max_speed <= 0:
            raise ValueError()
    except ValueError:
        msg = _('The configuration parameter <%(max_speed_name)s> must be set to a positive numerical value, '
                'but is currently set to <%(max_speed_value)s>.')
        msg = msg % {'max_speed_name': importer_constants.KEY_MAX_SPEED, 'max_speed_value': max_speed}
        raise configuration_utils.ValidationError(msg)


def _validate_num_threads(config):
    """
    Make sure the num_threads value is a positive integer, if it is set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    num_threads = config.get(importer_constants.KEY_MAX_DOWNLOADS)
    if num_threads is None:
        # We don't require num_threads to be set
        return

    try:
        num_threads = _cast_to_int_without_allowing_floats(num_threads)
        if num_threads < 1:
            raise ValueError()
    except ValueError:
        msg = _('The configuration parameter <%(num_threads_name)s> must be set to a positive integer, but '
                'is currently set to <%(num_threads)s>.')
        msg = msg % {'num_threads_name': importer_constants.KEY_MAX_DOWNLOADS, 'num_threads': num_threads}
        raise configuration_utils.ValidationError(msg)


def _validate_proxy_password(config):
    """
    The proxy_password setting is optional. However, if it is set, it must be a string. Also, if it is set,
    proxy_user must also be set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    proxy_password = config.get(importer_constants.KEY_PROXY_PASS)
    if proxy_password is None and config.get(importer_constants.KEY_PROXY_USER) is None:
        # Proxy password is not required
        return
    elif proxy_password is None:
        # If proxy_password is set, proxy_username must also be set
        msg = _('The configuration parameter <%(username_name)s> requires the <%(password_name)s> parameter '
                'to also be set.')
        msg = msg % {'password_name': importer_constants.KEY_PROXY_PASS,
                   'username_name': importer_constants.KEY_PROXY_USER}
        raise configuration_utils.ValidationError(msg)

    if not isinstance(proxy_password, basestring):
        msg = _('The configuration parameter <%(proxy_password_name)s> should be a string, but it was '
                '%(type)s.')
        msg = msg % {'proxy_password_name': importer_constants.KEY_PROXY_PASS, 'type': type(proxy_password)}
        raise configuration_utils.ValidationError(msg)


def _validate_proxy_port(config):
    """
    The proxy_port is optional. If it is set, this will make sure the proxy_url is also set, and that the port
    is a positive integer.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    proxy_port = config.get(importer_constants.KEY_PROXY_PORT)
    if proxy_port is None:
        # Proxy port is not required
        return

    try:
        proxy_port = _cast_to_int_without_allowing_floats(proxy_port)
        if proxy_port < 1:
            raise ValueError()
    except ValueError:
        msg = _('The configuration parameter <%(name)s> must be set to a positive integer, but is currently '
                'set to <%(value)s>.')
        msg = msg % {'name': importer_constants.KEY_PROXY_PORT, 'value': proxy_port}
        raise configuration_utils.ValidationError(msg)


def _validate_proxy_url(config):
    """
    Make sure the proxy_url is a string, if it is set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    dependencies = [importer_constants.KEY_PROXY_PASS, importer_constants.KEY_PROXY_PORT,
                    importer_constants.KEY_PROXY_USER]
    proxy_url = config.get(importer_constants.KEY_PROXY_HOST)
    if proxy_url is None and all([config.get(parameter) is None for parameter in dependencies]):
        # Proxy url is not required
        return
    elif proxy_url is None:
        msg = _('The configuration parameter <%(name)s> is required when any of the following other '
                'parameters are defined: ' + ', '.join(dependencies) + '.')
        msg = msg % {'name': importer_constants.KEY_PROXY_HOST}
        raise configuration_utils.ValidationError(msg)
    if not isinstance(proxy_url, basestring):
        msg = _('The configuration parameter <%(name)s> should be a string, but it was %(type)s.')
        msg = msg % {'name': importer_constants.KEY_PROXY_HOST, 'type': type(proxy_url)}
        raise configuration_utils.ValidationError(msg)


def _validate_proxy_username(config):
    """
    The proxy_username is optional. If it is set, this method will ensure that it is a string, and it will
    also ensure that the proxy_password and proxy_url settings are set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    proxy_username = config.get(importer_constants.KEY_PROXY_USER)
    # Proxy username is not required unless the password is set
    if proxy_username is None and config.get(importer_constants.KEY_PROXY_PASS) is None:
        return
    elif proxy_username is None:
        # If proxy_password is set, proxy_username must also be set
        msg = _('The configuration parameter <%(password_name)s> requires the <%(username_name)s> parameter '
                'to also be set.')
        msg = msg % {'password_name': importer_constants.KEY_PROXY_PASS,
                     'username_name': importer_constants.KEY_PROXY_USER}
        raise configuration_utils.ValidationError(msg)

    if not isinstance(proxy_username, basestring):
        msg = _('The configuration parameter <%(name)s> should be a string, but it was %(type)s.')
        msg = msg % {'name': importer_constants.KEY_PROXY_USER, 'type': type(proxy_username)}
        raise configuration_utils.ValidationError(msg)


def _validate_remove_missing_units(config):
    """
    This method will validate the optional config setting called "remove_missing_units". If it is set, it must
    be a boolean, otherwise it may be None.

    :param config: the config to be validated
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    configuration_utils.validate_non_required_bool(config, importer_constants.KEY_UNITS_REMOVE_MISSING)


def _validate_ssl_ca_cert(config):
    """
    Make sure the ssl_ca_cert is a string, if it is set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    ssl_ca_cert = config.get(importer_constants.KEY_SSL_CA_CERT)
    if ssl_ca_cert is None:
        # ssl_ca_cert is not required
        return
    if not isinstance(ssl_ca_cert, basestring):
        msg = _('The configuration parameter <%(name)s> should be a string, but it was %(type)s.')
        msg = msg % {'name': importer_constants.KEY_SSL_CA_CERT, 'type': type(ssl_ca_cert)}
        raise configuration_utils.ValidationError(msg)


def _validate_ssl_client_cert(config):
    """
    Make sure the ssl_client_cert is a string, if it is set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    ssl_client_cert = config.get(importer_constants.KEY_SSL_CLIENT_CERT)
    if ssl_client_cert is None and config.get(importer_constants.KEY_SSL_CLIENT_KEY) is None:
        # ssl_client_cert is not required
        return
    elif ssl_client_cert is None:
        # If the key is set, we should also have a cert
        msg = _('The configuration parameter <%(key_name)s> requires the <%(cert_name)s> parameter to also '
                'be set.')
        msg = msg % {'key_name': importer_constants.KEY_SSL_CLIENT_KEY, 'cert_name': importer_constants.KEY_SSL_CLIENT_CERT}
        raise configuration_utils.ValidationError(msg)

    if not isinstance(ssl_client_cert, basestring):
        msg = _('The configuration parameter <%(name)s> should be a string, but it was %(type)s.')
        msg = msg % {'name': importer_constants.KEY_SSL_CLIENT_CERT, 'type': type(ssl_client_cert)}
        raise configuration_utils.ValidationError(msg)


def _validate_ssl_client_key(config):
    """
    Make sure the ssl_client_key is a string and that the cert is also provided, if the key is set.

    :param config: The configuration object that we are validating.
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    ssl_client_key = config.get(importer_constants.KEY_SSL_CLIENT_KEY)
    if ssl_client_key is None:
        # ssl_client_key is not required
        return

    if not isinstance(ssl_client_key, basestring):
        msg = _('The configuration parameter <%(name)s> should be a string, but it was %(type)s.')
        msg = msg % {'name': importer_constants.KEY_SSL_CLIENT_KEY, 'type': type(ssl_client_key)}
        raise configuration_utils.ValidationError(msg)


def _validate_validate_downloads(config):
    """
    This (humorously named) method will validate the optional config option called
    "validate_downloads". If it is set, it must be a boolean, otherwise it may be None.

    :param config: the config to be validated
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    configuration_utils.validate_non_required_bool(config, importer_constants.KEY_VALIDATE)
