from gettext import gettext as _

from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.repo.upload import MetadataException, UploadCommand
from pulp.client.extensions.extensions import PulpCliOption

from pulp_rpm.common.ids import TYPE_ID_PKG_LANGPACKS


NAME = 'langpacks'
DESC = _('creates a new package langpacks')

d = _('name field to include in the package langpacks; must be specified with the '
      '`install` option. multiple may be indicated by specifying the argument '
      'multiple times. Coresponds with a single `install` field sequentially in order given')
OPT_NAME = PulpCliOption('--name', d, aliases=['-n'], allow_multiple=True, required=True)

d = _('install field to include in the package langpacks; must be specified with the '
      '`name` option. multiple may be indicated by specifying the argument '
      'multiple times. Coresponds with a single `name` field sequentially in order given.')
OPT_INSTALL = PulpCliOption('--install', d, aliases=['-i'], allow_multiple=True, required=True)


class CreatePackageLangpacksCommand(UploadCommand):
    """
    Handles the creation of a package langpacks.
    """

    def __init__(self, context, upload_manager, name=NAME, description=DESC):
        super(CreatePackageLangpacksCommand, self).__init__(context, upload_manager, name,
                                                            description, upload_files=False)
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

        self.add_option(OPT_NAME)
        self.add_option(OPT_INSTALL)

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

        return TYPE_ID_PKG_LANGPACKS

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
        return {'repo_id': repo_id}

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
        names = kwargs[OPT_NAME.keyword]
        installs = kwargs[OPT_INSTALL.keyword]

        if len(names) != len(installs):
            msg = _('Package Langpacks requires equal number `name` and `install` arguments.')
            raise MetadataException(msg)

        metadata = {
            'matches': []
        }

        for name, install in zip(names, installs):
            metadata['matches'].append({'name': name, 'install': install})

        return metadata
