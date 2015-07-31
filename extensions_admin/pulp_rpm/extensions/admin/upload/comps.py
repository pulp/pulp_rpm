from gettext import gettext as _

from pulp.client.commands.repo.upload import UploadCommand
from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP


NAME_XML = 'comps'
DESC_XML = _('uploads comps.xml into a repository')
SUFFIX_XML = '.xml'


class _CreateCompsCommand(UploadCommand):
    """
    Base command for uploading comps.xml. This shouldn't be instantiated directly
    outside of this module in favor of one of the type-specific subclasses.
    """

    def __init__(self, context, upload_manager, type_id, suffix, name, description):
        """
        :param context: Pulp client context
        :type  context: pulp.client.extensions.core.ClientContext
        :param upload_manager: created and configured upload manager instance
        :type  upload_manager: pulp.client.upload.manager.UploadManager
        :param type_id: ID of the type of the file being uploaded
        :type  type_id: str
        :param suffix: suffix of the comps xml file
        :type  suffix: str
        :param name: The name to use for this command
        :type  name: str
        :param description: The description for this command
        :type  description: str
        """

        super(_CreateCompsCommand, self).__init__(context, upload_manager, name=name,
                                                  description=description)
        self.type_id = type_id
        self.suffix = suffix

    def determine_type_id(self, filename, **kwargs):
        """
        Returns the ID of the type of file being uploaded, used by the server
        to determine the correct plugin to handle the upload.

        :param filename: full path to the file being uploaded
        :type  filename: str
        :param kwargs: arguments passed into the upload call by the user
        :type  kwargs: dict

        :return: ID of the type of file being uploaded
        :rtype:  str
        """

        return self.type_id

    def matching_files_in_dir(self, directory):
        """
        Returns which files in the given directory should be uploaded.

        :param directory: directory in which to list files
        :type  directory: str

        :return: list of full paths of comp.xml files to upload
        :rtype:  list
        """

        all_files_in_dir = super(_CreateCompsCommand, self).matching_files_in_dir(directory)
        comps = [f for f in all_files_in_dir if f.endswith(self.suffix)]
        return comps

    def generate_unit_key(self, filename, **kwargs):
        """
        For the given file, returns the unit key that should be specified in
        the upload request.

        :param filename: full path to the file being uploaded
        :type  filename: str
        :param kwargs: arguments passed into the upload call by the user
        :type  kwargs: dict

        :return: unit key that should be uploaded for the file
        :rtype:  dict
        """

        return {}


class CreateCompsCommand(_CreateCompsCommand):

    def __init__(self, context, upload_manager, name=NAME_XML, description=DESC_XML):
        super(CreateCompsCommand, self).__init__(context, upload_manager, TYPE_ID_PKG_GROUP,
                                                 SUFFIX_XML, name, description)
