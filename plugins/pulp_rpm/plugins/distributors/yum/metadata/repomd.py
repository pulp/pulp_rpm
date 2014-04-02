import gzip
import hashlib
import os
import time
from xml.etree import ElementTree

from pulp_rpm.common.constants import CONFIG_DEFAULT_CHECKSUM
from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    MetadataFileContext, REPO_DATA_DIR_NAME, REPOMD_FILE_NAME)

from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

REPO_XML_NAME_SPACE = 'http://linux.duke.edu/metadata/repo'
RPM_XML_NAME_SPACE = 'http://linux.duke.edu/metadata/rpm'


class RepomdXMLFileContext(MetadataFileContext):

    def __init__(self, working_dir, checksum_type=CONFIG_DEFAULT_CHECKSUM):

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, REPOMD_FILE_NAME)
        super(RepomdXMLFileContext, self).__init__(metadata_file_path, checksum_type)

    def __exit__(self, exc_type, exc_val, exc_tb):

        super(RepomdXMLFileContext, self).__exit__(exc_type, exc_val, exc_tb)

        # If we've exited under an error condition, delete the partially written
        # metadata file to avoid publishing a partially functioning repository,
        # which is worse than publishing a completely broken one.
        if any((exc_type, exc_val, exc_tb)):
            os.unlink(self.metadata_file_path)

    def _write_root_tag_open(self):

        repomd_attributes = {'xmlns': REPO_XML_NAME_SPACE,
                             'xmlns:rpm': RPM_XML_NAME_SPACE}

        repomd_element = ElementTree.Element('repomd', repomd_attributes)

        revision_element = ElementTree.SubElement(repomd_element, 'revision')
        revision_element.text = str(int(time.time()))

        bogus_element = ElementTree.SubElement(repomd_element, '')

        repomd_element_string = ElementTree.tostring(repomd_element, 'utf-8')

        bogus_element_string = ElementTree.tostring(bogus_element, 'utf-8')

        opening_tag, closing_tag = repomd_element_string.split(bogus_element_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        # Setup the corresponding _write_root_tag_close as a closure

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_metadata_file_metadata(self, data_type, file_path, precalculated_checksum=None):

        file_name = os.path.basename(file_path)

        # If the file is a symbolic link, make sure we generate the the metadata
        # based on the actual file, not the link itself.
        if os.path.islink(file_path):
            file_path = os.readlink(file_path)

        data_attributes = {'type': data_type}
        data_element = ElementTree.Element('data', data_attributes)

        location_element = ElementTree.SubElement(data_element, 'location')
        location_element.text = os.path.join(REPO_DATA_DIR_NAME, file_name)

        timestamp_element = ElementTree.SubElement(data_element, 'timestamp')
        timestamp_element.text = str(os.path.getmtime(file_path))

        size_element = ElementTree.SubElement(data_element, 'size')
        size_element.text = str(os.path.getsize(file_path))

        checksum_attributes = {'type': self.checksum_type}
        checksum_element = ElementTree.SubElement(data_element, 'checksum', checksum_attributes)

        # if checksum is calculated in the individual repodata file's context, use it instead of
        # calculating it again.
        if precalculated_checksum is None:
            with open(file_path, 'rb') as file_handle:
                content = file_handle.read()
                checksum_element.text = self.checksum_constructor(content).hexdigest()
        else:
            checksum_element.text = precalculated_checksum

        if file_path.endswith('.gz'):

            open_size_element = ElementTree.SubElement(data_element, 'open-size')

            open_checksum_attributes = {'type': self.checksum_type}
            open_checksum_element = ElementTree.SubElement(data_element, 'open-checksum', open_checksum_attributes)

            try:
                file_handle = gzip.open(file_path, 'r')

            except:
                # cannot have an else clause to the try without an except clause
                raise

            else:
                try:
                    content = file_handle.read()
                    open_size_element.text = str(len(content))
                    open_checksum_element.text = self.checksum_constructor(content).hexdigest()

                finally:
                    file_handle.close()

        # Write the metadata out as a utf-8 string

        data_element_string = ElementTree.tostring(data_element, 'utf-8')

        _LOG.debug('Writing repomd metadata:\n' + data_element_string)

        self.metadata_file_handle.write(data_element_string + '\n')


