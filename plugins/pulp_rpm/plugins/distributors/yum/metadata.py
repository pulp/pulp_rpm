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

import os
from gettext import gettext as _

from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

REPODATA_DIR_NAME = 'repodata'
PRIMARY_XML_FILE_NAME = 'primary.xml'

# -- base metadata file context class ------------------------------------------

class MetadataFileContext(object):

    def __init__(self, metadata_file_path):
        self.metadata_file_path = metadata_file_path
        self.metadata_file_handle = None

    def __enter__(self):
        self._open_metadata_file_handle()
        self._write_opening_tag()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._write_closing_tag()
        self._close_metadata_file_handle()

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

        self.metadata_file_handle = open(self.metadata_file_path, 'w')

    def _close_metadata_file_handle(self):
        assert self.metadata_file_handle is not None

        self.metadata_file_handle.flush()
        self.metadata_file_handle.close()

    def _write_opening_tag(self):
        raise NotImplementedError()

    def _write_closing_tag(self):
        raise NotImplementedError()

# -- primary.xml file context class --------------------------------------------

class PrimaryXMLFileContext(MetadataFileContext):

    def __init__(self, working_dir):
        metadata_file_path = os.path.join(working_dir, REPODATA_DIR_NAME, PRIMARY_XML_FILE_NAME)
        super(PrimaryXMLFileContext, self).__init__(metadata_file_path)

    def _write_opening_tag(self):
        pass

    def _write_closing_tag(self):
        pass

    def add_unit_metadata(self, unit):
        pass

