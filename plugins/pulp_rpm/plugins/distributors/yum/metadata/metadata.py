from gettext import gettext as _

from pulp.plugins.util.metadata_writer import MetadataFileContext as PlatformMetadataFileContext
from pulp_rpm.yum_plugin import util

# import this for backward compatibility, it was originally in this module but moved to platform
from pulp.plugins.util.metadata_writer import HASHLIB_ALGORITHMS  # NOQA

_LOG = util.getLogger(__name__)

REPO_DATA_DIR_NAME = 'repodata'
REPOMD_FILE_NAME = 'repomd.xml'


class MetadataFileContext(PlatformMetadataFileContext):
    """
    Context manager class for metadata file generation, with a tiny bit of special knowledge
    about yum repo metadata files, which is to not prepend the repomd.xml file with a checksum.
    """

    def __init__(self, metadata_file_path, checksum_type=None, non_checksum_filenames=None):
        """
        :param metadata_file_path: full path to metadata file to be generated
        :type  metadata_file_path: str
        :param checksum_type: checksum type to be used to generate and prepend checksum
                              to the file names of repodata files. If checksum_type is None,
                              no checksum is added to the filename
        :type checksum_type: str or None
        :param non_checksum_filenames: file names that *will not* have a checksum prepended to them
        :type non_checksum_filenames: list or None
        """
        super(MetadataFileContext, self).__init__(
            metadata_file_path, checksum_type, non_checksum_filenames)

        # this subclass exists to ensure that the repomd file doesn't get a checksum prepended
        if REPOMD_FILE_NAME not in self.non_checksum_filenames:
            self.non_checksum_filenames.append(REPOMD_FILE_NAME)


# -- pre-generated metadata context --------------------------------------------

class PreGeneratedMetadataContext(MetadataFileContext):
    """
    Intermediate context manager for metadata files that have had their content
    pre-generated and stored on the unit model.
    """

    def _add_unit_pre_generated_metadata(self, metadata_category, unit):
        """
        Write a unit's pre-generated metadata, from the given metadata category,
        into the metadata file.

        :param metadata_category: metadata category to get pre-generated metadata for
        :type  metadata_category: str
        :param unit: unit whose metadata is being written
        :type  unit: pulp.plugins.model.Unit
        """
        _LOG.debug('Writing pre-generated %s metadata for unit: %s' %
                   (metadata_category, unit.unit_key.get('name', 'unknown')))

        if 'repodata' not in unit.metadata or metadata_category not in unit.metadata['repodata']:
            msg = _('No pre-generated metadata found for unit [%(u)s], [%(c)s]')
            _LOG.error(msg % {'u': str(unit.unit_key), 'c': metadata_category})

            return

        metadata = unit.metadata['repodata'][metadata_category]

        if not isinstance(metadata, basestring):
            msg = _('%(c)s metadata for [%(u)s] must be a string, but is a %(t)s')
            _LOG.error(
                msg % {'c': metadata_category.title(), 'u': unit.id, 't': str(type(metadata))})

            return

        # this should already be unicode if it came from the db
        # but, you know, testing...
        metadata = unicode(metadata)
        self.metadata_file_handle.write(metadata.encode('utf-8'))

    def add_unit_metadata(self, unit):
        """
        Write the metadata for a given unit to the file handle.

        :param unit: unit whose metadata is being written
        :type  unit: pulp.plugins.model.Unit
        """
        raise NotImplementedError()
