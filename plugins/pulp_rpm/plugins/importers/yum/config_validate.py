from gettext import gettext as _

from pulp.plugins.util import importer_config


def validate(config):
    """
    Validates a potential configuration for the yum importer.

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: tuple of valid flag and error message
    :rtype:  (bool, str)
    """

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
