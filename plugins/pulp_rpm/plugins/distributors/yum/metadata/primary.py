import os
from xml.dom import pulldom

from pulp.plugins.util.metadata_writer import FastForwardXmlFileContext

from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

PRIMARY_XML_FILE_NAME = 'primary.xml.gz'
COMMON_NAMESPACE = 'http://linux.duke.edu/metadata/common'
RPM_NAMESPACE = 'http://linux.duke.edu/metadata/rpm'


class PrimaryXMLFileContext(FastForwardXmlFileContext):
    """
    Context manager for generating the primary.xml.gz metadata file.
    """

    def __init__(self, working_dir, num_units, checksum_type=None):
        """
        :param working_dir: working directory to create the primary.xml.gz in
        :type  working_dir: str
        :param num_units: total number of units whose metadata will be written
                          into the primary.xml.gz metadata file, or the number of packages added
        :type  num_units: int
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, PRIMARY_XML_FILE_NAME)
        self.num_packages = num_units
        attributes = {'xmlns': COMMON_NAMESPACE,
                      'xmlns:rpm': RPM_NAMESPACE,
                      'packages': str(self.num_packages)}
        super(PrimaryXMLFileContext, self).__init__(metadata_file_path, 'metadata',
                                                    root_attributes=attributes,
                                                    checksum_type=checksum_type)

    def initialize(self):
        """
        Initialize all the file handles and fast forward the xml to the point where we should
        start adding content
        """
        super(PrimaryXMLFileContext, self).initialize()
        # Fast Forward to where we can start writing
        if self.fast_forward:
            for event in self.xml_generator:
                if event[0] == pulldom.START_ELEMENT and event[1].nodeName == 'metadata':
                    # Get the current packages count and add it to the previous
                    package_count = int(event[1].attributes['packages'].value)
                    package_count += self.num_packages
                    event[1].attributes['packages'].value = str(package_count)
                elif event[0] == pulldom.END_ELEMENT and event[1].nodeName == 'metadata':
                    # break out and insert more stuff here
                    break

    def add_unit_metadata(self, unit):
        """
        Add the metadata to primary.xml.gz for the given unit.

        :param unit: unit whose metadata is to be written
        :type  unit: pulp.plugins.model.Unit
        """
        metadata = unit.metadata['repodata']['primary']
        self.metadata_file_handle.write(metadata)

