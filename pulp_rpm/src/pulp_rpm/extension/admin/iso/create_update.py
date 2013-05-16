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
import os

from pulp.client import arg_utils, parsers
from pulp.client.commands import options as std_options
from pulp.client.commands.repo.cudl import CreateRepositoryCommand
from pulp.client.commands.repo.importer_config import ImporterConfigMixin, safe_parse
from pulp.client.extensions.extensions import PulpCliOption, PulpCliOptionGroup
from pulp.common import constants as pulp_constants

from pulp_rpm.common import constants, ids


class ISODistributorConfigMixin(object):
    def __init__(self):
        self.publishing_group = PulpCliOptionGroup(_('Publishing'))
        self.authorization_group = PulpCliOptionGroup(_('Client Authorization'))

        d = _('if "true", the repository will be published over the HTTP protocol')
        self.opt_http = PulpCliOption('--serve-http', d, required=False,
                                      parse_func=parsers.parse_boolean)
        d = _('if "true", the repository will be published over the HTTPS protocol')
        self.opt_https = PulpCliOption('--serve-https', d, required=False,
                                       parse_func=parsers.parse_boolean)

        self.publishing_group.add_option(self.opt_http)
        self.publishing_group.add_option(self.opt_https)

        self.add_option_group(self.publishing_group)

    def parse_distributor_config(self, user_input):
        """
        Generate an ISODistributor configuration based on the given parameters (user input).

        :param user_input: The keys and values passed to the CLI by the user
        :type  user_input: dict
        """
        key_tuples = (
            (constants.CONFIG_SERVE_HTTP, self.opt_http.keyword),
            (constants.CONFIG_SERVE_HTTPS, self.opt_https.keyword),
        )

        config = {}
        for config_key, input_key in key_tuples:
            safe_parse(user_input, config, input_key, config_key)

        return config


class ISORepoCreateCommand(CreateRepositoryCommand, ImporterConfigMixin, ISODistributorConfigMixin):
    """
    This is the create command for ISO repositories.
    """
    def __init__(self, context):
        """
        Call the __init__ methods for both of our superclasses.
        """
        # Add standard create options
        CreateRepositoryCommand.__init__(self, context)

        # Add sync-related options to the create command
        ImporterConfigMixin.__init__(self, include_sync=True, include_ssl=True, include_proxy=True,
                                     include_throttling=True, include_unit_policy=True)

        ISODistributorConfigMixin.__init__(self)

    def run(self, **kwargs):
        """
        Run the repository creation.
        """
        # Turn missing options to None
        arg_utils.convert_removed_options(kwargs)

        repo_id = kwargs.pop(std_options.OPTION_REPO_ID.keyword)
        description = kwargs.pop(std_options.OPTION_DESCRIPTION.keyword, None)
        display_name = kwargs.pop(std_options.OPTION_NAME.keyword, None)
        notes = kwargs.pop(std_options.OPTION_NOTES.keyword, None) or {}

        # Mark this as an ISO repository
        notes[pulp_constants.REPO_NOTE_TYPE_KEY] = constants.REPO_NOTE_ISO

        # Build the importer and distributor configs
        try:
            importer_config = self.parse_user_input(kwargs)
            distributor_config = self.parse_distributor_config(kwargs)
        except arg_utils.InvalidConfig, e:
            self.prompt.render_failure_message(str(e))
            return os.EX_DATAERR

        distributors = [
            {'distributor_type': ids.TYPE_ID_DISTRIBUTOR_ISO, 'distributor_config': distributor_config,
             'auto_publish': True, 'distributor_id': ids.TYPE_ID_DISTRIBUTOR_ISO}]
        self.context.server.repo.create_and_configure(repo_id, display_name, description, notes,
                                                      ids.TYPE_ID_IMPORTER_ISO, importer_config, distributors)

        msg = _('Successfully created repository [%(r)s]') % {'r': repo_id}
        self.prompt.render_success_message(msg)