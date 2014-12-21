from gettext import gettext as _


class ValidationError(ValueError):
    pass


def validate_non_required_bool(config, setting_name):
    """
    Validate that the setting keyed in the config by setting_name is either not set, or if it is
    set that
    it is a boolean value.

    :param config:       the config to be validated
    :type  config:       pulp.plugins.config.PluginCallConfiguration
    :param setting_name: The name of the setting we wish to validate in the config
    :type  setting_name: basestring
    """
    original_setting = setting = config.get(setting_name)
    if setting is None:
        # We don't require any settings
        return
    if isinstance(setting, basestring):
        setting = config.get_boolean(setting_name)
    if isinstance(setting, bool):
        return
    msg = _('The configuration parameter <%(name)s> may only be set to a boolean value, but is '
            'currently set to <%(value)s>.')
    msg = msg % {'name': setting_name, 'value': original_setting}
    raise ValidationError(msg)
