from gettext import gettext as _
import logging

from pulp_rpm.common import constants
from pulp_rpm.plugins import configuration_utils
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
    # This is a tuple of tuples. The inner tuples have two elements. The first element is a
    # validation method
    # that should be run, and the second element is the name of the config setting that should be
    #  validated by
    # it.
    validations = (
        (configuration_utils.validate_non_required_bool, constants.CONFIG_SERVE_HTTP,),
        (configuration_utils.validate_non_required_bool, constants.CONFIG_SERVE_HTTPS,),
        (_validate_ssl_cert, constants.CONFIG_SSL_AUTH_CA_CERT),
    )

    for validation in validations:
        try:
            validation[0](config, validation[1])
        except configuration_utils.ValidationError, e:
            return False, str(e)

    return True, None


def _validate_ssl_cert(config, setting_name):
    """
    Ensure that the setting_name from config is a valid SSL certificate, if it is given. This
    setting is not
    required.

    :param config:       The config to validate
    :type  config:       pulp.plugins.config.PluginCallConfiguration
    :param setting_name: The name of the setting that needs to be validated
    :type  setting_name: str
    """
    ssl_cert = config.get(setting_name)
    if not ssl_cert:
        # The cert is not required
        return
    if not yum_utils.validate_cert(ssl_cert):
        msg = _("The SSL certificate <%(s)s> is not a valid certificate.")
        msg = msg % {'s': setting_name}
        raise configuration_utils.ValidationError(msg)
