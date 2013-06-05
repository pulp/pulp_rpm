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

from copy import deepcopy

from pulp.client.commands.criteria import DisplayUnitAssociationsCommand

from pulp_rpm.common import ids


class ISOSearchCommand(DisplayUnitAssociationsCommand):
    """
    This command allows the user to find out which ISOs are in a given repository.
    """
    # These are the fields we should display to the user about an ISO, in order
    ISO_FIELDS = ['name', 'size', 'checksum']

    def __init__(self, context, *args, **kwargs):
        super(ISOSearchCommand, self).__init__(self.search_isos, *args, **kwargs)
        self.context = context

    def search_isos(self, **user_input):
        """
        Perform the search against the Pulp server.

        :param user_input: The input given from the user
        :type  user_input: dict
        """
        search_params = deepcopy(user_input)

        repo_id = search_params.pop('repo-id')
        search_params['type_ids'] = [ids.TYPE_ID_ISO]

        isos = self.context.server.repo_unit.search(repo_id, **search_params).response_body

        if user_input.get(self.ASSOCIATION_FLAG.keyword):
            # The user requested --details, so we'll need to do some massaging of the data
            for iso in isos:
                for key in iso['metadata'].keys():
                    # Remove all the fields from metadata that aren't part of ISO_FIELDS
                    if key not in self.ISO_FIELDS:
                        del iso['metadata'][key]
            # Only display these fields to the user, in this order
            display_filter = ['metadata', 'updated', 'repo_id', 'created', 'unit_id',
                              'unit_type_id', 'owner_type', 'id', 'owner_id']
        else:
            # The user did not request details, so let's only show them the metadata and the fields
            # that are particular to an ISO
            isos = [i['metadata'] for i in isos]
            display_filter = self.ISO_FIELDS

        self.context.prompt.render_document_list(isos, filters=display_filter,
                                                 order=display_filter)
