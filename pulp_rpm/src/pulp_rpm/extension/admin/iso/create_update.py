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

from pulp.client import arg_utils
from pulp.client.commands import options as std_options
from pulp.client.commands.repo.cudl import CreateRepositoryCommand
from pulp.client.commands.repo.importer_config import ImporterConfigMixin
from pulp.common import constants as pulp_constants

from pulp_rpm.common import constants, ids


class ISORepoCreateCommand(CreateRepositoryCommand, ImporterConfigMixin):
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
        except arg_utils.InvalidConfig, e:
            self.prompt.render_failure_message(str(e))
            return os.EX_DATAERR

        distributors = [
            dict(distributor_type=ids.TYPE_ID_DISTRIBUTOR_YUM,
                 distributor_config=yum_distributor_config,
                 auto_publish=True, distributor_id=ids.YUM_DISTRIBUTOR_ID),
            dict(distributor_type=ids.TYPE_ID_DISTRIBUTOR_EXPORT,
                 distributor_config=export_distributor_config,
                 auto_publish=False, distributor_id=ids.EXPORT_DISTRIBUTOR_ID)
        ]
        self.context.server.repo.create_and_configure(repo_id, display_name, description, notes,
                                                      ids.TYPE_ID_IMPORTER_ISO, importer_config, distributors)

        msg = _('Successfully created repository [%(r)s]') % {'r': repo_id}
        self.prompt.render_success_message(msg)
