import logging

from gettext import gettext as _

from pulp.common.plugins import importer_constants
from pulp.plugins.util import importer_config
from pulp_rpm.common import constants

_logger = logging.getLogger(__name__)


def validate(config):
    """
    Validates a potential configuration for the yum importer.

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: tuple of valid flag and error message
    :rtype:  (bool, str)
    """
    config = config.flatten()  # squish it into a dictionary so we can manipulate it
    error_messages = []

    validations = (
        _validate_allowed_keys,
        _validate_lazy_compatibility,
    )

    for v in validations:
        v(config, error_messages)

    if error_messages:
        for msg in error_messages:
            _logger.error(msg)

        return False, '\n'.join(error_messages)

    try:
        importer_config.validate_config(config)
        return True, None

    except importer_config.InvalidConfig, e:
        # Concatenate all of the failure messages into a single message
        msg = _('Configuration errors:\n')
        for failure_message in e.failure_messages:
            msg += failure_message + '\n'
        msg = msg.rstrip()  # remove the trailing \n
        return False, msg


def _validate_allowed_keys(config, error_messages):
    """
    Validates that passed signature keys have proper length.

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :param error_messages: accumulated list of errors encountered during importer config validation
    :type error_messages: list
    """

    allowed_keys = config.get(constants.CONFIG_ALLOWED_KEYS, [])
    for key in allowed_keys:
        if len(key) != 8:
            msg = _('Signature key %s should be 8 characters long') % key
            error_messages.append(msg)


def _validate_lazy_compatibility(config, error_messages):
    """
    Validates lazy sync and signature policy compatibility.
    To extract the signature information from a package, we need it to have been downloaded.

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :param error_messages: accumulated list of errors encountered during importer config validation
    :type error_messages: list
    """

    download_policy = config.get(importer_constants.DOWNLOAD_POLICY,
                                 importer_constants.DOWNLOAD_IMMEDIATE)
    require_signature = config.get(constants.CONFIG_REQUIRE_SIGNATURE, False)
    allowed_keys = config.get(constants.CONFIG_ALLOWED_KEYS)
    if download_policy != importer_constants.DOWNLOAD_IMMEDIATE and \
            (require_signature or allowed_keys):
        msg = _('%s download policy and signature check are not compatible') % download_policy
        error_messages.append(msg)
