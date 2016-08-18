from gettext import gettext as _
import logging
import os

from pulp_rpm.common import constants
from pulp_rpm.plugins import configuration_utils
from pulp_rpm.yum_plugin import util as yum_utils
from pulp_rpm.plugins.distributors.yum.configuration import _check_for_relative_path_conflicts


logger = logging.getLogger(__name__)


def validate(config, repo, config_conduit):
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
        (_validate_relative_url, constants.RELATIVE_URL_KEYWORD, repo, config_conduit)
    )

    for validation in validations:
        try:
            validation[0](config, *validation[1:])
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


def _validate_relative_url(config, setting_name, repo, config_conduit):
    """
    Ensure that the setting_name from config is a valid relative URL path. This setting is not
    required.

    :param config: The config to validate
    :type  config:       pulp.plugins.config.PluginCallConfiguration
    :param setting_name: The name of the setting that needs to be validated
    :type  setting_name: str
    :param repo: The repository that will use the distributor
    :type  repo: pulp.plugins.model.Repository
    :param config_conduit: Configuration Conduit;
    :type config_conduit: pulp.plugins.conduits.repo_validate.RepoConfigConduit
    """
    relative_url = config.get(setting_name)
    if relative_url is None:
        return

    if not isinstance(relative_url, basestring):
        msg = _('Configuration value for [relative_url] must be a string, but is a %(t)s')
        raise configuration_utils.ValidationError(msg % {'t': str(type(relative_url))})

    elif os.path.isabs(relative_url):
        msg = _("Value for [relative_url]  must be be a relative path: %s" % relative_url)
        raise configuration_utils.ValidationError(msg % {'r': relative_url})
    error_message = []
    _check_for_relative_path_conflicts(repo, config, config_conduit, error_message)
    if error_message:
        raise configuration_utils.ValidationError(error_message[0])
