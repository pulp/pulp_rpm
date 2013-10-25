# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import gzip
import os
import traceback
from gettext import gettext as _
from xml.etree import ElementTree

from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

REPO_DATA_DIR_NAME = 'repodata'

FILE_LISTS_XML_FILE_NAME = 'filelists.xml.gz'
OTHER_XML_FILE_NAME = 'other.xml.gz'
PRIMARY_XML_FILE_NAME = 'primary.xml.gz'
UPDATE_INFO_XML_FILE_NAME = 'updateinfo.xml.gz'

COMMON_NAMESPACE = 'http://linux.duke.edu/metadata/common'
FILE_LISTS_NAMESPACE = 'http://linux.duke.edu/metadata/filelists'
OTHER_NAMESPACE = 'http://linux.duke.edu/metadata/other'
RPM_NAMESPACE = 'http://linux.duke.edu/metadata/rpm'

# -- base metadata file context class ------------------------------------------

class MetadataFileContext(object):
    """
    Context manager class for metadata file generation.
    """

    def __init__(self, metadata_file_path):
        """
        :param metadata_file_path: full path to metadata file to be generated
        :type  metadata_file_path: str
        """

        self.metadata_file_path = metadata_file_path
        self.metadata_file_handle = None

    def __del__(self):
        # try to finalize in cause something bad happened
        self.finalize()

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
        if self.metadata_file_handle is None:
            # finalize has already been run or initialize has not been run
            return

        self._write_root_tag_close()
        self._close_metadata_file_handle()

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
        assert self.metadata_file_handle is not None
        _LOG.debug('Closing metadata file: %s' % self.metadata_file_path)

        self.metadata_file_handle.flush()
        self.metadata_file_handle.close()

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
            _LOG.error(msg % {'c': metadata_category.title(), 'u': unit.id, 't': str(type(metadata))})

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

# -- filelists.xml file context class ------------------------------------------

class FilelistsXMLFileContext(PreGeneratedMetadataContext):
    """
    Context manager for generating the filelists.xml.gz file.
    """

    def __init__(self, working_dir, num_units):
        """
        :param working_dir: working directory to create the filelists.xml.gz in
        :type  working_dir: str
        :param num_units: total number of units whose metadata will be written
                          into the filelists.xml.gz metadata file
        :type  num_units: int
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, FILE_LISTS_XML_FILE_NAME)
        super(FilelistsXMLFileContext, self).__init__(metadata_file_path)

        self.num_packages = num_units

    def _write_root_tag_open(self):

        attributes = {'xmlns': FILE_LISTS_NAMESPACE,
                      'packages': str(self.num_packages)}

        metadata_element = ElementTree.Element('filelists', attributes)
        bogus_element = ElementTree.SubElement(metadata_element, '')

        metadata_tags_string = ElementTree.tostring(metadata_element, 'utf-8')
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = metadata_tags_string.split(bogus_tag_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_unit_metadata(self, unit):

        self._add_unit_pre_generated_metadata('filelists', unit)

# -- other.xml file context class ----------------------------------------------

class OtherXMLFileContext(PreGeneratedMetadataContext):
    """
    Context manager for generating the other.xml.gz file.
    """

    def __init__(self, working_dir, num_units):
        """
        :param working_dir: working directory to create the other.xml.gz in
        :type  working_dir: str
        :param num_units: total number of units whose metadata will be written
                          into the other.xml.gz metadata file
        :type  num_units: int
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, OTHER_XML_FILE_NAME)
        super(OtherXMLFileContext, self).__init__(metadata_file_path)

        self.num_packages = num_units

    def _write_root_tag_open(self):

        attributes = {'xmlns': OTHER_NAMESPACE,
                      'packages': str(self.num_packages)}

        metadata_element = ElementTree.Element('otherdata', attributes)
        bogus_element = ElementTree.SubElement(metadata_element, '')

        metadata_tags_string = ElementTree.tostring(metadata_element, 'utf-8')
        # use a bogus sub-element to programmaticly split the opening and closing tags
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = metadata_tags_string.split(bogus_tag_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_unit_metadata(self, unit):

        self._add_unit_pre_generated_metadata('other', unit)

# -- primary.xml file context class --------------------------------------------

class PrimaryXMLFileContext(PreGeneratedMetadataContext):
    """
    Context manager for generating the primary.xml.gz metadata file.
    """

    def __init__(self, working_dir, num_units):
        """
        :param working_dir: working directory to create the primary.xml.gz in
        :type  working_dir: str
        :param num_units: total number of units whose metadata will be written
                          into the primary.xml.gz metadata file
        :type  num_units: int
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, PRIMARY_XML_FILE_NAME)
        super(PrimaryXMLFileContext, self).__init__(metadata_file_path)

        self.num_packages = num_units

    def _write_root_tag_open(self):

        attributes = {'xmlns': COMMON_NAMESPACE,
                      'xmlns:rpm': RPM_NAMESPACE,
                      'packages': str(self.num_packages)}

        metadata_element = ElementTree.Element('metadata', attributes)
        # use a bogus sub-element to programmaticly split the opening and closing tags
        bogus_element = ElementTree.SubElement(metadata_element, '')

        metadata_tags_string = ElementTree.tostring(metadata_element, 'utf-8')
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = metadata_tags_string.split(bogus_tag_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        # create the closing tag method on the fly
        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_unit_metadata(self, unit):
        """
        Add the metadata to primary.xml.gz for the given unit.

        :param unit: unit whose metadata is to be written
        :type  unit: pulp.plugins.model.Unit
        """

        self._add_unit_pre_generated_metadata('primary', unit)

# -- updateinfo.xml file context -----------------------------------------------

class UpdateinfoXMLFileContext(MetadataFileContext):

    def __init__(self, working_dir):

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, UPDATE_INFO_XML_FILE_NAME)
        super(UpdateinfoXMLFileContext, self).__init__(metadata_file_path)

    def _write_root_tag_open(self):

        self.metadata_file_handle.write('<updates>\n')

    def _write_root_tag_close(self):

        self.metadata_file_handle.write('</updates>\n')

    def add_unit_metadata(self, erratum_unit):

        update_attributes = {'status': erratum_unit.metadata['status'],
                             'type': erratum_unit.metadata['type'],
                             'version': erratum_unit.metadata['version'],
                             'from': erratum_unit.metadata.get('from', '')}
        update_element = ElementTree.Element('update', update_attributes)

        id_element = ElementTree.SubElement(update_element, 'id')
        id_element.text = erratum_unit.unit_key['id']

        issued_attributes = {'date': erratum_unit.metadata['issued']}
        issued_element = ElementTree.SubElement(update_element, 'issued', issued_attributes)

        reboot_element = ElementTree.SubElement(update_element, 'reboot_suggested')
        reboot_element.text = str(erratum_unit.metadata['reboot_suggested'])

        for key in ('title', 'release', 'rights', 'description', 'solution',
                    'severity', 'summary', 'pushcount'):

            value = erratum_unit.metadata.get(key)

            if not value:
                continue

            sub_element = ElementTree.SubElement(update_element, key)
            sub_element.text = value

        updated = erratum_unit.metadata.get('updated')

        if updated:
            updated_attributes = {'date': updated}
            updated_element = ElementTree.SubElement(update_element, 'updated', updated_attributes)

        references_element = ElementTree.SubElement(update_element, 'references')

        for reference in erratum_unit.metadata.get('references'):

            reference_attributes = {'id': reference['id'] or '',
                                    'title': reference['title'] or '',
                                    'type': reference['type'],
                                    'href': reference['href']}
            reference_element = ElementTree.SubElement(references_element, 'reference', reference_attributes)

        for pkglist in erratum_unit.metadata.get('pkglist', []):

            pkglist_element = ElementTree.SubElement(update_element, 'pkglist')

            collection_attributes = {}
            short = pkglist.get('short')
            if short is not None:
                collection_attributes['short'] = short
            collection_element = ElementTree.SubElement(pkglist_element, 'collection', collection_attributes)

            name_element = ElementTree.SubElement(collection_element, 'name')
            name_element.text = pkglist['name']

            for package in pkglist['packages']:

                package_attributes = {'name': package['name'],
                                      'version': package['version'],
                                      'release': package['release'],
                                      'epoch': package['epoch'] or '0',
                                      'arch': package['arch'],
                                      'src': package.get('src', '')}
                package_element = ElementTree.SubElement(collection_element, 'package', package_attributes)

                filename_element = ElementTree.SubElement(package_element, 'filename')
                filename_element.text = package['filename']

                checksum_type, checksum_value = package['sum']
                sum_attributes = {'type': checksum_type}
                sum_element = ElementTree.SubElement(package_element, 'sum', sum_attributes)
                sum_element.text = checksum_value

                reboot_element = ElementTree.SubElement(package_element, 'reboot_suggested')
                reboot_element.text = str(package.get('reboot_suggested', False))

        # write the top-level XML element out to the file

        update_element_string = ElementTree.tostring(update_element, 'utf-8')

        _LOG.debug('Writing updateinfo unit metadata:\n' + update_element_string)

        self.metadata_file_handle.write(update_element_string + '\n')

