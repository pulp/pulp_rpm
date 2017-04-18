from gettext import gettext as _

from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.repo.upload import UploadCommand
from pulp.client.extensions.extensions import PulpCliOption

from pulp_rpm.common.ids import TYPE_ID_PKG_ENVIRONMENT


NAME = 'environment'
DESC = _('creates a new package environment')

d = _('id of the package environment')
OPT_ENV_ID = PulpCliOption('--environment-id', d, aliases=['-i'], required=True)

d = _('name of the package environment')
OPT_NAME = PulpCliOption('--name', d, aliases=['-n'], required=True)

d = _('description of the package environment')
OPT_DESCRIPTION = PulpCliOption('--description', d, aliases=['-d'], required=True)

d = _('display order for the package environment')
OPT_ORDER = PulpCliOption('--display-order', d, allow_multiple=False, required=False, default=0)

d = _('package group IDs to include in the package environment; multiple may '
      'be indicated by specifying the argument multiple times')
OPT_GROUP = PulpCliOption('--group', d, aliases=['-g'], allow_multiple=True, required=False)


class CreatePackageEnvironmentCommand(UploadCommand):
    """
    Handles the creation of a package environment.
    """

    def __init__(self, context, upload_manager, name=NAME, description=DESC):
        super(CreatePackageEnvironmentCommand, self).__init__(context, upload_manager,
                                                              name, description,
                                                              upload_files=False)

        self.add_option(OPT_ENV_ID)
        self.add_option(OPT_NAME)
        self.add_option(OPT_DESCRIPTION)
        self.add_option(OPT_ORDER)
        self.add_option(OPT_GROUP)

    def determine_type_id(self, filename, **kwargs):
        return TYPE_ID_PKG_ENVIRONMENT

    def generate_unit_key(self, filename, **kwargs):
        repo_id = kwargs[OPTION_REPO_ID.keyword]
        env_id = kwargs[OPT_ENV_ID.keyword]
        unit_key = {'id': env_id, 'repo_id': repo_id}
        return unit_key

    def generate_metadata(self, filename, **kwargs):
        name = kwargs[OPT_NAME.keyword]
        description = kwargs[OPT_DESCRIPTION.keyword]
        display_order = kwargs[OPT_ORDER.keyword]
        group_ids = kwargs[OPT_GROUP.keyword]

        metadata = {
            'name': name,
            'description': description,
            'display_order': display_order,
            'group_ids': group_ids,
            'translated_description': {},
            'translated_name': {},
            'options': []
        }
        return metadata
