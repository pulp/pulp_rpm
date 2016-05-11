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

d = _('display order for the package environment. Defaults to 1024')
OPT_ORDER = PulpCliOption('--display-order', d, allow_multiple=False, required=False, default=1024)

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
        """
        :param context: Pulp client context
        :type  context: pulp.client.extensions.core.ClientContext
        :param upload_manager: created and configured upload manager instance
        :type  upload_manager: pulp.client.upload.manager.UploadManager
        :param name: The name of the command
        :type  name: str
        :param description: The description of the command
        :type  description: str
        :param upload_files: if false, the user will not be prompted for files
               to upload and the create will be purely metadata based
        :type  upload_files: bool
        """

        self.add_option(OPT_ENV_ID)
        self.add_option(OPT_NAME)
        self.add_option(OPT_DESCRIPTION)
        self.add_option(OPT_ORDER)
        self.add_option(OPT_GROUP)

    def determine_type_id(self, filename, **kwargs):
        """
        Returns the ID of the type of file being uploaded.

        :param filename: full path to the file being uploaded
        :type  filename: str
        :param kwargs: arguments passed into the upload call by the user
        :type  kwargs: dict

        :return: ID of the type of file being uploaded
        :rtype:  str
        """

        return TYPE_ID_PKG_ENVIRONMENT

    def generate_unit_key(self, filename, **kwargs):
        """
        For the given file, returns the unit key that should be specified in
        the upload request.

        :param filename: full path to the file being uploaded
        :type  filename: str, None
        :param kwargs: arguments passed into the upload call by the user
        :type  kwargs: dict

        :return: unit key that should be uploaded for the file
        :rtype:  dict
        """

        repo_id = kwargs[OPTION_REPO_ID.keyword]
        env_id = kwargs[OPT_ENV_ID.keyword]
        unit_key = {'id': env_id, 'repo_id': repo_id}
        return unit_key

    def generate_metadata(self, filename, **kwargs):
        """
        For the given file, returns a list of metadata that should be included
        as part of the upload request.

        :param filename: full path to the file being uploaded
        :type  filename: str, None
        :param kwargs: arguments passed into the upload call by the user
        :type  kwargs: dict

        :return: metadata information that should be uploaded for the file
        :rtype:  dict
        """

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
