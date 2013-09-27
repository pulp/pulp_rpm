# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
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
import hashlib
import os
import rpm
import sys

from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.repo.upload import UploadCommand, MetadataException
from pulp.client.extensions.extensions import PulpCliFlag
from pulp_rpm.common.ids import TYPE_ID_RPM


NAME = 'rpm'
DESC = _('uploads one or more RPMs into a repository')

DESC_SKIP_EXISTING = _('if specified, RPMs that already exist on the server will not be uploaded')
FLAG_SKIP_EXISTING = PulpCliFlag('--skip-existing', DESC_SKIP_EXISTING)

RPMTAG_NOSOURCE = 1051
CHECKSUM_READ_BUFFER_SIZE = 65536


class CreateRpmCommand(UploadCommand):
    """
    Handles initializing and uploading one or more RPMs.
    """

    def __init__(self, context, upload_manager, name=NAME, description=DESC):
        super(CreateRpmCommand, self).__init__(context, upload_manager, name=name, description=description)

        self.add_flag(FLAG_SKIP_EXISTING)

    def determine_type_id(self, filename, **kwargs):
        return TYPE_ID_RPM

    def matching_files_in_dir(self, directory):
        all_files_in_dir = super(CreateRpmCommand, self).matching_files_in_dir(directory)
        rpms = [f for f in all_files_in_dir if f.endswith('.rpm')]
        return rpms

    def generate_unit_key(self, filename, **kwargs):
        unit_key = _generate_unit_key(filename)
        return unit_key

    def create_upload_list(self, file_bundles, **kwargs):

        # Only check if the user requests it
        if not kwargs.get(FLAG_SKIP_EXISTING.keyword, False):
            return file_bundles

        self.prompt.write(_('Checking for existing RPMs on the server...'))

        repo_id = kwargs[OPTION_REPO_ID.keyword]

        bundles_to_upload = []
        for bundle in file_bundles:
            filters = {
                'name' : bundle.unit_key['name'],
                'version' : bundle.unit_key['version'],
                'release' : bundle.unit_key['release'],
                'epoch' : bundle.unit_key['epoch'],
                'arch' : bundle.unit_key['arch'],
                'checksumtype' : bundle.unit_key['checksumtype'],
                'checksum' : bundle.unit_key['checksum'],
            }

            criteria = {
                'type_ids' : [TYPE_ID_RPM],
                'filters' : filters,
            }

            existing = self.context.server.repo_unit.search(repo_id, **criteria).response_body
            if len(existing) == 0:
                bundles_to_upload.append(bundle)

        self.prompt.write(_('... completed'))
        self.prompt.render_spacer()

        return bundles_to_upload


def _generate_unit_key(rpm_filename):
    """
    For the given RPM, analyzes its metadata to generate the appropriate unit
    key.

    :param rpm_filename: full path to the RPM to analyze
    :type  rpm_filename: str

    :return: unit key for the RPM being uploaded
    :rtype:  dict
    """

    # Expected unit key fields:
    # "name", "epoch", "version", "release", "arch", "checksumtype", "checksum"

    unit_key = dict()

    # Read the RPM header attributes for use later
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    fd = os.open(rpm_filename, os.O_RDONLY)
    try:
        headers = ts.hdrFromFdno(fd)
        os.close(fd)
    except rpm.error:
        # Raised if the headers cannot be read
        os.close(fd)
        msg = _('The given file is not a valid RPM')
        raise MetadataException(msg), None, sys.exc_info()[2]

    # -- Unit Key -----------------------

    # Checksum
    unit_key['checksumtype'] = 'sha256' # hardcoded to this in v1 so leaving this way for now
    unit_key['checksum'] = _calculate_checksum(unit_key['checksumtype'], rpm_filename)

    # Name, Version, Release, Epoch
    for k in ['name', 'version', 'release', 'epoch']:
        unit_key[k] = headers[k]

    #   Epoch munging
    if unit_key['epoch'] is None:
        unit_key['epoch'] = str(0)
    else:
        unit_key['epoch'] = str(unit_key['epoch'])

    # Arch
    if headers['sourcepackage']:
        if RPMTAG_NOSOURCE in headers.keys():
            unit_key['arch'] = 'nosrc'
        else:
            unit_key['arch'] = 'src'
    else:
        unit_key['arch'] = headers['arch']

    return unit_key


def _calculate_checksum(checksum_type, filename):
    m = hashlib.new(checksum_type)
    f = open(filename, 'r')
    while 1:
        file_buffer = f.read(CHECKSUM_READ_BUFFER_SIZE)
        if not file_buffer:
            break
        m.update(file_buffer)
    f.close()
    return m.hexdigest()
