import hashlib
import gzip
import os
import traceback
from gettext import gettext as _

from pulp_rpm.yum_plugin import util

_LOG = util.getLogger(__name__)

HASHLIB_ALGORITHMS = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')
REPO_DATA_DIR_NAME = 'repodata'
REPOMD_FILE_NAME = 'repomd.xml'


class MetadataFileContext(object):
    """
    Context manager class for metadata file generation.
    """

    def __init__(self, metadata_file_path, checksum_type=None):
        """
        :param metadata_file_path: full path to metadata file to be generated
        :type  metadata_file_path: str
        :param checksum_type: checksum type to be used to generate and prepend checksum
                              to the file names of repodata files. If checksum_type is None,
                              no checksum is added to the filename
        :type checksum_type: str or None
        """

        self.metadata_file_path = metadata_file_path
        self.metadata_file_handle = None
        self.checksum_type = checksum_type
        self.checksum = None
        if self.checksum_type is not None:
            assert checksum_type in HASHLIB_ALGORITHMS
            self.checksum_constructor = getattr(hashlib, checksum_type)

    # -- for use with 'with' ---------------------------------------------------

    def __enter__(self):

        self.initialize()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if None not in (exc_type, exc_val, exc_tb):
            err_msg = '\n'.join(traceback.format_exception(exc_type, exc_val, exc_tb))
            log_msg = _('Exception occurred while writing [%(m)s]\n%(e)s')
            # any errors here should have already been caught and logged
            _LOG.debug(log_msg % {'m': self.metadata_file_path, 'e': err_msg})

        self.finalize()

        return True

    # -- context lifecycle -----------------------------------------------------

    def initialize(self):
        """
        Create the new metadata file and write the XML header and opening root
        level tag into it.
        """
        if self.metadata_file_handle is not None:
            # initialize has already, at least partially, been run
            return

        self._open_metadata_file_handle()
        self._write_xml_header()
        self._write_root_tag_open()

    def finalize(self):
        """
        Write the closing root level tag into the metadata file and close it.
        """
        if self._is_closed(self.metadata_file_handle):
            # finalize has already been run or initialize has not been run
            return

        try:
            self._write_root_tag_close()

        except Exception, e:
            _LOG.exception(e)

        try:
            self._close_metadata_file_handle()

        except Exception, e:
            _LOG.exception(e)

        # Add calculated checksum to the repodata filename except for repomd file.
        file_name = os.path.basename(self.metadata_file_path)
        if self.checksum_type is not None and file_name != REPOMD_FILE_NAME:
            with open(self.metadata_file_path, 'rb') as file_handle:
                content = file_handle.read()
                checksum = self.checksum_constructor(content).hexdigest()

            self.checksum = checksum
            file_name_with_checksum = checksum + '-' + file_name
            new_file_path = os.path.join(os.path.dirname(self.metadata_file_path),
                                         file_name_with_checksum)
            os.rename(self.metadata_file_path, new_file_path)
            self.metadata_file_path = new_file_path

    # -- metadata file lifecycle -----------------------------------------------

    def _open_metadata_file_handle(self):
        """
        Open the metadata file handle, creating any missing parent directories.

        If the file already exists, this will overwrite it.
        """
        assert self.metadata_file_handle is None
        _LOG.debug('Opening metadata file: %s' % self.metadata_file_path)

        if not os.path.exists(self.metadata_file_path):

            parent_dir = os.path.dirname(self.metadata_file_path)

            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, mode=0770)

            elif not os.access(parent_dir, os.R_OK | os.W_OK | os.X_OK):
                msg = _('Insufficient permissions to write metadata file in directory [%(d)s]')
                raise RuntimeError(msg % {'d': parent_dir})

        else:

            msg = _('Overwriting existing metadata file [%(p)s]')
            _LOG.warn(msg % {'p': self.metadata_file_path})

            if not os.access(self.metadata_file_path, os.R_OK | os.W_OK):
                msg = _('Insufficient permissions to overwrite [%(p)s]')
                raise RuntimeError(msg % {'p': self.metadata_file_path})

        msg = _('Opening metadata file handle for [%(p)s]')
        _LOG.debug(msg % {'p': self.metadata_file_path})

        if self.metadata_file_path.endswith('.gz'):
            self.metadata_file_handle = gzip.open(self.metadata_file_path, 'w')

        else:
            self.metadata_file_handle = open(self.metadata_file_path, 'w')

    def _write_xml_header(self):
        """
        Write the initial <?xml?> header tag into the file handle.
        """
        assert self.metadata_file_handle is not None
        _LOG.debug('Writing XML header into metadata file: %s' % self.metadata_file_path)

        # XXX hackish and ugly, I'm sure there's a library routine to do this
        xml_header = u'<?xml version="1.0" encoding="UTF-8"?>\n'.encode('utf-8')
        self.metadata_file_handle.write(xml_header)

    def _write_root_tag_open(self):
        """
        Write the opening tag for the root element of a given metadata XML file.
        """
        raise NotImplementedError()

    def _write_root_tag_close(self):
        """
        Write the closing tag for the root element of a give metadata XML file.
        """
        raise NotImplementedError()

    def _close_metadata_file_handle(self):
        """
        Flush any cached writes to the metadata file handle and close it.
        """
        if not self._is_closed(self.metadata_file_handle):
            _LOG.debug('Closing metadata file: %s' % self.metadata_file_path)
            self.metadata_file_handle.flush()
            self.metadata_file_handle.close()

    @staticmethod
    def _is_closed(file_object):
        """
        Determine if the file object has been closed. If it is None, it is assumed to be closed.

        :param file_object: a file object
        :type  file_object: file

        :return:    True if the file object is closed or is None, otherwise False
        :rtype:     bool
        """
        if file_object is None:
            # finalize has already been run or initialize has not been run
            return True

        try:
            return file_object.closed
        except AttributeError:
            # python 2.6 doesn't have a "closed" attribute on a GzipFile,
            # so we must look deeper.
            if isinstance(file_object, gzip.GzipFile):
                return file_object.myfileobj is None or file_object.myfileobj.closed
            else:
                raise


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
