from gettext import gettext as _
import hashlib
import os
import sys

import rpm
from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.repo.upload import UploadCommand, MetadataException
from pulp.client.extensions.extensions import PulpCliFlag

from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM
from pulp_rpm.extensions.admin.repo_options import OPT_CHECKSUM_TYPE


NAME_RPM = 'rpm'
DESC_RPM = _('uploads one or more RPMs into a repository')
SUFFIX_RPM = '.rpm'

NAME_SRPM = 'srpm'
DESC_SRPM = _('uploads one or more SRPMs into a repository')
SUFFIX_SRPM = '.src.rpm'

NAME_DRPM = 'drpm'
DESC_DRPM = _('uploads one or more DRPMs into a repository')
SUFFIX_DRPM = '.drpm'

DESC_SKIP_EXISTING = _('if specified, RPMs that already exist on the server will not be uploaded')
FLAG_SKIP_EXISTING = PulpCliFlag('--skip-existing', DESC_SKIP_EXISTING)

RPMTAG_NOSOURCE = 1051
CHECKSUM_READ_BUFFER_SIZE = 65536


class _CreatePackageCommand(UploadCommand):
    """
    Base command for uploading RPMs, SRPMs and DRPMs. This shouldn't be instantiated directly
    outside of this module in favor of one of the type-specific subclasses.
    """

    def __init__(self, context, upload_manager, type_id, suffix, name, description):
        super(_CreatePackageCommand, self).__init__(context, upload_manager, name=name,
                                                    description=description)

        self.type_id = type_id
        self.suffix = suffix

        self.add_flag(FLAG_SKIP_EXISTING)

    def determine_type_id(self, filename, **kwargs):
        return self.type_id

    def matching_files_in_dir(self, directory):
        all_files_in_dir = super(_CreatePackageCommand, self).matching_files_in_dir(directory)
        rpms = [f for f in all_files_in_dir if f.endswith(self.suffix)]
        return rpms

    def generate_unit_key_and_metadata(self, filename, **kwargs):
        # These are extracted server-side, so nothing to do here.
        metadata = {}
        if kwargs.get(OPT_CHECKSUM_TYPE.keyword, None) is not None:
            metadata['checksumtype'] = kwargs[OPT_CHECKSUM_TYPE.keyword]
        return {}, metadata

    def create_upload_list(self, file_bundles, **kwargs):

        # In most cases, this will simply return the list of file bundles to be uploaded.
        # The entries in that list will have None for both key and metadata as it is
        # extracted server-side.
        # However, if the user elects to skip existing, we need to extract the unit keys
        # for the query to the server. After that initial check, the remainder of this
        # method handles that.

        # Return what the framework generated if we don't need to analyze existing RPMs.
        if not kwargs.get(FLAG_SKIP_EXISTING.keyword, False):
            return file_bundles

        self.prompt.write(_('Checking for existing RPMs on the server...'))

        repo_id = kwargs[OPTION_REPO_ID.keyword]

        bundles_to_upload = []
        for bundle in file_bundles:

            # The key is no longer in the bundle by default (it's extracted server-side),
            # but it's needed for this check, so generate it here.
            try:
                unit_key = _generate_unit_key(bundle.filename)
            except MetadataException:
                if self.type_id != TYPE_ID_DRPM:
                    raise
                else:
                    self.prompt.warning(
                        _('%s: RPM only DRPMs are not supported.') % bundle.filename)
                    continue

            filters = {
                'version': unit_key['version'],
                'release': unit_key['release'],
                'epoch': unit_key['epoch'],
                'arch': unit_key['arch'],
                'checksumtype': unit_key['checksumtype'],
                'checksum': unit_key['checksum'],
            }
            if self.type_id != TYPE_ID_DRPM:
                filters['name'] = unit_key['name']
            else:
                filters['new_package'] = unit_key['name']

            criteria = {
                'type_ids': [TYPE_ID_RPM] if self.type_id != TYPE_ID_DRPM else [TYPE_ID_DRPM],
                'filters': filters,
            }

            existing = self.context.server.repo_unit.search(repo_id, **criteria).response_body
            if len(existing) == 0:
                # The original bundle (without the key or metadata) is still used, that way
                # we ensure the server-side plugin does the extraction and RPMs that were
                # uploaded with this check are not treated differently.
                bundles_to_upload.append(bundle)

        self.prompt.write(_('... completed'))
        self.prompt.render_spacer()

        return bundles_to_upload

    def succeeded(self, task):
        """
        Called when a task has completed with a status indicating success.
        Subclasses may override this to display a custom message to the user.

        :param task: full task report for the task being displayed
        :type  task: pulp.bindings.responses.Task
        """
        # Check for any errors in the details block of the task
        if task.result and task.result.get('details') and task.result.get('details').get('errors'):

            self.prompt.render_failure_message(_('Task Failed'))
            for error in task.result.get('details').get('errors'):
                self.prompt.render_failure_message(error)
        else:
            super(_CreatePackageCommand, self).succeeded(task)


class CreateRpmCommand(_CreatePackageCommand):
    def __init__(self, context, upload_manager, name=NAME_RPM, description=DESC_RPM):
        super(CreateRpmCommand, self).__init__(context, upload_manager, TYPE_ID_RPM,
                                               SUFFIX_RPM, name, description)
        self.add_option(OPT_CHECKSUM_TYPE)


class CreateSrpmCommand(_CreatePackageCommand):
    def __init__(self, context, upload_manager, name=NAME_SRPM, description=DESC_SRPM):
        super(CreateSrpmCommand, self).__init__(context, upload_manager, TYPE_ID_SRPM,
                                                SUFFIX_SRPM, name, description)
        self.add_option(OPT_CHECKSUM_TYPE)


class CreateDrpmCommand(_CreatePackageCommand):
    def __init__(self, context, upload_manager, name=NAME_DRPM, description=DESC_DRPM):
        super(CreateDrpmCommand, self).__init__(context, upload_manager, TYPE_ID_DRPM,
                                                SUFFIX_DRPM, name, description)
        self.add_option(OPT_CHECKSUM_TYPE)


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
    unit_key['checksumtype'] = 'sha256'  # hardcoded to this in v1 so leaving this way for now
    unit_key['checksum'] = _calculate_checksum(unit_key['checksumtype'], rpm_filename)

    # Name, Version, Release, Epoch
    for k in ['name', 'version', 'release', 'epoch']:
        unit_key[k] = headers[k]

    # Epoch munging
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
