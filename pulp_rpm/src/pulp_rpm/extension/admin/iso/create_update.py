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
from pulp.client.commands.repo.cudl import CreateRepositoryCommand, UpdateRepositoryCommand
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
        d = _('full path to the CA certificate that should be used to verify client authorization '
              'certificates; setting this turns on client authorization for the repository')
        self.opt_auth_ca = PulpCliOption('--auth-ca', d, required=False)

        self.publishing_group.add_option(self.opt_http)
        self.publishing_group.add_option(self.opt_https)
        self.authorization_group.add_option(self.opt_auth_ca)

        self.add_option_group(self.publishing_group)
        self.add_option_group(self.authorization_group)

    def _parse_distributor_config(self, user_input):
        """
        Generate an ISODistributor configuration based on the given parameters (user input).

        :param user_input: The keys and values passed to the CLI by the user
        :type  user_input: dict
        """
        key_tuples = (
            (constants.CONFIG_SERVE_HTTP, self.opt_http.keyword),
            (constants.CONFIG_SERVE_HTTPS, self.opt_https.keyword),
            (constants.CONFIG_SSL_AUTH_CA_CERT, self.opt_auth_ca.keyword),
        )

        config = {}
        for config_key, input_key in key_tuples:
            safe_parse(user_input, config, input_key, config_key)

        arg_utils.convert_file_contents((constants.CONFIG_SSL_AUTH_CA_CERT,), config)

        return config


class ISORepoCreateUpdateMixin(ImporterConfigMixin, ISODistributorConfigMixin):
    def __init__(self):
        """
        Call the __init__ methods for both of our superclasses.
        """
        # Add sync-related options to the create command
        ImporterConfigMixin.__init__(self, include_sync=True, include_ssl=True, include_proxy=True,
                                     include_throttling=True, include_unit_policy=True)

        ISODistributorConfigMixin.__init__(self)

    def populate_unit_policy(self):
        """
        Adds options to the unit policy group. This is only called if the include_unit_policy flag
        is set to True in the constructor. We are overriding this from ImportConfigMixin because the
        ISOImporter doesn't support the --retain-old-count option
        """
        self.unit_policy_group.add_option(self.options_bundle.opt_remove_missing)

    def run(self, **user_input):
        """
        Run the repository creation.
        """
        # Turn missing options to None
        arg_utils.convert_removed_options(user_input)

        repo_id = user_input.pop(std_options.OPTION_REPO_ID.keyword)
        description = user_input.pop(std_options.OPTION_DESCRIPTION.keyword, None)
        display_name = user_input.pop(std_options.OPTION_NAME.keyword, None)
        notes = user_input.pop(std_options.OPTION_NOTES.keyword, None) or {}

        # Mark this as an ISO repository
        notes[pulp_constants.REPO_NOTE_TYPE_KEY] = constants.REPO_NOTE_ISO

        # Build the importer and distributor configs
        try:
            importer_config = self.parse_user_input(user_input)
            distributor_config = self._parse_distributor_config(user_input)
        except arg_utils.InvalidConfig, e:
            self.prompt.render_failure_message(str(e), tag='create-failed')
            return os.EX_DATAERR

        distributors = [
            {'distributor_type': ids.TYPE_ID_DISTRIBUTOR_ISO, 'distributor_config': distributor_config,
             'auto_publish': True, 'distributor_id': ids.TYPE_ID_DISTRIBUTOR_ISO}]
        self._perform_command(repo_id, display_name, description, notes, importer_config, distributors)


class ISORepoCreateCommand(ISORepoCreateUpdateMixin, CreateRepositoryCommand):
    """
    This is the create command for ISO repositories.
    """
    def __init__(self, context):
        """
        Call the __init__ methods for both of our superclasses.
        """
        # Add standard create options
        CreateRepositoryCommand.__init__(self, context)

        ISORepoCreateUpdateMixin.__init__(self)

    def _perform_command(self, repo_id, display_name, description, notes,
                         importer_config, distributors):
        self.context.server.repo.create_and_configure(repo_id, display_name, description, notes,
                                                      ids.TYPE_ID_IMPORTER_ISO, importer_config, distributors)

        msg = _('Successfully created repository [%(r)s]') % {'r': repo_id}
        self.prompt.render_success_message(msg, tag='repo-created')


class ISORepoUpdateCommand(ISORepoCreateUpdateMixin, UpdateRepositoryCommand):
    """
    This is the update command for ISO repositories.
    """
    def __init__(self, context):
        """
        Call the __init__ methods fo both superclasses.
        """
        UpdateRepositoryCommand.__init__(self, context)

        ISORepoCreateUpdateMixin.__init__(self)

    def _perform_command(self, repo_id, display_name, description, notes,
                         importer_config, distributors):
        distributor_configs = {}
        for distributor in distributors:
            distributor_configs[distributor['distributor_id']] = distributor['distributor_config']

        response = self.context.server.repo.update_repo_and_plugins(
            repo_id, display_name, description, notes,
            importer_config, distributor_configs)

        if not response.is_async():
            msg = _('Repository [%(r)s] successfully updated')
            self.prompt.render_success_message(msg % {'r' : repo_id}, tag='repo-updated')
        else:
            msg = _('Repository update postponed due to another operation. '
                    'Progress on this task can be viewed using the commands '
                    'under "repo tasks"')
            self.prompt.render_paragraph(msg, tag='update-postponed')
            self.prompt.render_reasons(response.response_body.reasons)