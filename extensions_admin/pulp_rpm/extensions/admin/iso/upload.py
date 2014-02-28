# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from gettext import gettext as _
import os

from pulp_rpm.common import file_utils
from pulp.client.commands.repo.upload import UploadCommand
from pulp_rpm.common import ids


NAME = 'upload'
DESCRIPTION = _('uploads one or more ISOs into a repository')


class UploadISOCommand(UploadCommand):
    def __init__(self, context, upload_manager):
        """
        Initialize the UploadISOCommand.
        """
        super(UploadISOCommand, self).__init__(context, upload_manager, name=NAME,
                                               description=DESCRIPTION)

    @staticmethod
    def determine_type_id(filename, **kwargs):
        """
        This method always returns the ISO type.

        :param filename: unused
        :type  filename: basestring
        :param kwargs:   unused keyword args
        :type  kwargs:   dict
        :return:         ids.TYPE_ID
        :rtype:          str
        """
        return ids.TYPE_ID_ISO

    @staticmethod
    def generate_unit_key_and_metadata(filepath, **kwargs):
        """
        Analyze the ISO found at the path specified by filepath, and return its unit_key and
        metadata as a 2-tuple. Since ISOs don't have metadata, this just amounts to the unit key and
        an empty metadata dict.

        :param filepath: The path of the file that we need the unit key and metadata for
        :type  filepath: str
        :param kwargs:   Unused keyword arguments
        :type  kwargs:   dict
        :return:         A two tuple of (unit_key, metadata), both dicts
        :rtype:          tuple
        """
        iso = open(filepath)
        try:
            size = file_utils.calculate_size(iso)
            checksum = file_utils.calculate_checksum(iso)
        finally:
            iso.close()
        return {'name': os.path.basename(filepath), 'size': size, 'checksum': checksum}, {}
