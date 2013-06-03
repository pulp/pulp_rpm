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
