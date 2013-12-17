# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
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

class ValidationError(ValueError):
    pass


def validate_non_required_bool(config, setting_name):
    """
    Validate that the setting keyed in the config by setting_name is either not set, or if it is set that
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