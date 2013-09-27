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

REPODATA_DIR_NAME = 'repodata'
PRIMARY_XML_FILE_NAME = 'primary.xml.gz'

COMMON_NAMESPACE = 'http://linux.duke.edu/metadata/common'
RPM_NAMESPACE = 'http://linux.duke.edu/metadata/rpm'

# -- base metadata file context class ------------------------------------------

class MetadataFileContext(object):

    def __init__(self, metadata_file_path):

        self.metadata_file_path = metadata_file_path
        self.metadata_file_handle = None

    # -- for use with 'with' ---------------------------------------------------

    def __enter__(self):

        self.initialize()

    def __exit__(self, exc_type, exc_val, exc_tb):

        if None not in (exc_type, exc_val, exc_tb):

            err_msg = '\n'.join(traceback.format_exception(exc_type, exc_val, exc_tb))
            log_msg = _('Exception occurred while writing [%(m)s]\n%(e)s')
            # XXX should I make this 'debug'?
            # any errors here should have already been caught and logged
            _LOG.error(log_msg % {'m': self.metadata_file_path, 'e': err_msg})

        self.finalize()

    # -- context lifecycle -----------------------------------------------------

    def initialize(self):

        self._open_metadata_file_handle()
        self._write_xml_header()
        self._write_opening_tag()

    def finalize(self):

        self._write_closing_tag()
        self._close_metadata_file_handle()

    # -- metadata file lifecycle -----------------------------------------------

    def _open_metadata_file_handle(self):
        assert self.metadata_file_handle is None

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
        assert self.metadata_file_handle is not None
        # XXX hackish and ugly, I'm sure there's a library routine to do this
        xml_header = u'<?xml version="1.0" encoding="UTF-8"?>\n'.encode('utf-8')
        self.metadata_file_handle.write(xml_header)

    def _write_opening_tag(self):
        raise NotImplementedError()

    def _write_closing_tag(self):
        raise NotImplementedError()

    def _close_metadata_file_handle(self):
        assert self.metadata_file_handle is not None

        self.metadata_file_handle.flush()
        self.metadata_file_handle.close()

# -- pre-generated metadata context --------------------------------------------

class PreGeneratedMetadataContext(MetadataFileContext):

    def _add_unit_pre_generated_metadata(self, metadata_category, unit):

        metadata = unit.repodata.get(metadata_category, None)

        if not isinstance(metadata, unicode):

            msg = _('%(c)s metadata for [%(u)s] must be unicode, but is a %(t)s')
            _LOG.error(msg % {'c': metadata_category.title(), 'u': unit.id, 't': str(type(metadata))})

            return

        self.metadata_file_handle.write(metadata.encode('utf-8'))

# -- primary.xml file context class --------------------------------------------

class PrimaryXMLFileContext(PreGeneratedMetadataContext):

    def __init__(self, working_dir, num_packages):

        metadata_file_path = os.path.join(working_dir, REPODATA_DIR_NAME, PRIMARY_XML_FILE_NAME)
        super(PrimaryXMLFileContext, self).__init__(metadata_file_path)

        self.num_packages = num_packages

    def _write_opening_tag(self):

        attributes = {'xmlns': COMMON_NAMESPACE,
                      'xmlns:rpm': RPM_NAMESPACE,
                      'packages': self.num_packages}

        metadata_element = ElementTree.Element('metadata', attributes)
        # add a bogus sub-element to make splitting the opening and closing tags possible
        bogus_element = ElementTree.SubElement(metadata_element, '')

        metadata_tags_string = ElementTree.tostring(metadata_element, 'utf-8')
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = metadata_tags_string.split(bogus_tag_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        # create the closing tag method on the fly
        def _write_closing_tag_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_closing_tag = _write_closing_tag_closure

    def add_unit_metadata(self, unit):

        self._add_unit_pre_generated_metadata('primary', unit)

