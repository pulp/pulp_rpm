import hashlib
import os

from pulp.plugins.util.metadata_writer import MetadataFileContext
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common.constants import CONFIG_DEFAULT_CHECKSUM
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

MODULES_FILE_NAME = 'modules.yaml.gz'


# Note that this is "MetadataFileContext" from the core plugin API, not from
# pulp_rpm.plugin.distributors.yum.metadata.metadata
class ModulesFileContext(MetadataFileContext):

    def __init__(self, working_dir, checksum_type=CONFIG_DEFAULT_CHECKSUM):
        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, MODULES_FILE_NAME)
        super(ModulesFileContext, self).__init__(metadata_file_path, checksum_type)

    def initialize(self):
        super(ModulesFileContext, self).initialize()

    def finalize(self):
        super(ModulesFileContext, self).finalize()

    def add_document(self, document, doc_checksum):
        checksum = hashlib.sha256(document).hexdigest()
        if checksum == doc_checksum:
            self.metadata_file_handle.write(document)
        else:
            raise PulpCodedException(error_codes.RPM1017)
