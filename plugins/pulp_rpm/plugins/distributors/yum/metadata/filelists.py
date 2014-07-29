import os

from pulp.plugins.util.metadata_writer import FastForwardXmlFileContext

from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME


FILE_LISTS_XML_FILE_NAME = 'filelists.xml.gz'
FILE_LISTS_NAMESPACE = 'http://linux.duke.edu/metadata/filelists'


class FilelistsXMLFileContext(FastForwardXmlFileContext):
    """
    Context manager for generating the filelists.xml.gz file.
    """

    def __init__(self, working_dir, num_units, checksum_type=None):
        """
        :param working_dir: working directory to create the filelists.xml.gz in
        :type  working_dir: str
        :param num_units: total number of units whose metadata will be written
                          into the filelists.xml.gz metadata file, or the number of packages added
        :type  num_units: int
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, FILE_LISTS_XML_FILE_NAME)
        self.num_packages = num_units
        attributes = {'xmlns': FILE_LISTS_NAMESPACE,
                      'packages': str(self.num_packages)}
        super(FilelistsXMLFileContext, self).__init__(metadata_file_path, 'filelists',
                                                      search_tag='package',
                                                      root_attributes=attributes,
                                                      checksum_type=checksum_type)

    def add_unit_metadata(self, unit):
        """
        Add the metadata to the xml file for the given unit.

        :param unit: unit whose metadata is to be written
        :type  unit: pulp.plugins.model.Unit
        """
        metadata = unit.metadata['repodata']['filelists']
        self.metadata_file_handle.write(metadata)
