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

    def generate_unit_key_and_metadata(self, filename, **kwargs):
        unit_key, metadata = _generate_rpm_data(filename)
        return unit_key, metadata

    def create_upload_list(self, file_bundles, **kwargs):

        # Only check if the user requests it
        if not kwargs.get(FLAG_SKIP_EXISTING.keyword, False):
            return file_bundles

        self.prompt.write(_('Checking for existing RPMs on the server...'))

        repo_id = kwargs[OPTION_REPO_ID.keyword]

        bundles_to_upload = []
        for bundle in file_bundles:
            checksum = _calculate_checksum('sha256', bundle.filename)

            filters = {
                'name' : bundle.unit_key['name'],
                'version' : bundle.unit_key['version'],
                'release' : bundle.unit_key['release'],
                'epoch' : bundle.unit_key['epoch'],
                'arch' : bundle.unit_key['arch'],
                'checksumtype' : 'sha256',
                'checksum' : checksum,
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


def _generate_rpm_data(rpm_filename):
    """
    For the given RPM, analyzes its metadata to generate the appropriate unit
    key and metadata fields, returning both to the caller.

    This is performed client side instead of in the importer to get around
    differences in RPMs between RHEL 5 and later versions of Fedora. We can't
    guarantee the server will be able to properly read the RPM so it is
    read client-side and the metadata passed in.

    The obvious caveat is that the format of the returned values must match
    what the importer would produce had this RPM been synchronized from an
    external source.

    @param rpm_filename: full path to the RPM to analyze
    @type  rpm_filename: str

    @return: tuple of unit key and unit metadata for the RPM
    @rtype:  tuple
    """

    # Expected metadata fields:
    # "vendor", "description", "buildhost", "license", "vendor", "requires", "provides", "relativepath", "filename"
    #
    # Expected unit key fields:
    # "name", "epoch", "version", "release", "arch", "checksumtype", "checksum"

    unit_key = dict()
    metadata = dict()

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

    # -- Unit Metadata ------------------

    metadata['relativepath'] = os.path.basename(rpm_filename)
    metadata['filename'] = os.path.basename(rpm_filename)

    # This format is, and has always been, incorrect. As of the new yum importer, the
    # plugin will generate these from the XML snippet because the API into RPM headers
    # is atrocious. This is the end game for this functionality anyway, moving all of
    # that metadata derivation into the plugin, so this is just a first step.
    # I'm leaving these in and commented to show how not to do it.
    # metadata['requires'] = [(r,) for r in headers['requires']]
    # metadata['provides'] = [(p,) for p in headers['provides']]

    metadata['buildhost'] = headers['buildhost']
    metadata['license'] = headers['license']
    metadata['vendor'] = headers['vendor']
    metadata['description'] = headers['description']

    return unit_key, metadata


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
