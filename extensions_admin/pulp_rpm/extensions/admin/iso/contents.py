from copy import deepcopy

from pulp.client.commands.criteria import DisplayUnitAssociationsCommand
from pulp.client.commands.options import OPTION_REPO_ID

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

        repo_id = search_params.pop(OPTION_REPO_ID.keyword)
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
