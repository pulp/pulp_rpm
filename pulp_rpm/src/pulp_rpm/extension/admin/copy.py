# Copyright (c) 2012 Red Hat, Inc.
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
import sys

from pulp.bindings.exceptions import BadRequestException
from pulp.client import parsers
from pulp.client.commands.unit import UnitCopyCommand
from pulp.client.extensions.extensions import PulpCliOption

from pulp_rpm.common import ids, constants
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY

# -- constants ----------------------------------------------------------------

DESC_RPM = _('copy RPMs from one repository to another')
DESC_SRPM = _('copy SRPMs from one repository to another')
DESC_DRPM = _('copy DRPMs from one repository to another')
DESC_ERRATA = _('copy errata from one repository to another')
DESC_DISTRIBUTION = _('copy distributions from one repository to another')
DESC_PKG_GROUP = _('copy package groups from one repository to another')
DESC_PKG_CATEGORY = _('copy package categories from one repository to another')

COPY_CHILD_RPMS_OPTION = PulpCliOption(
    '--copy-children', _('copy child RPMs (default: True)'),
    required=False, default='true', parse_func=parsers.parse_boolean)

COPY_CHILD_GROUPS_OPTION = PulpCliOption(
    '--copy-children', _('copy child groups (default: True)'),
    required=False, default='true', parse_func=parsers.parse_boolean)

# -- commands -----------------------------------------------------------------

class RpmCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def rpm_copy(**kwargs):
            # let's not load ALL of the metadata, as that could take a tremendous
            # amount of RAM
            kwargs['fields'] = ids.UNIT_KEY_RPM
            return _copy(self.context, TYPE_ID_RPM, **kwargs)
        super(RpmCopyCommand, self).__init__(rpm_copy, name='rpm', description=DESC_RPM)


class SrpmCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def srpm_copy(**kwargs):
            return _copy(self.context, TYPE_ID_SRPM, **kwargs)
        super(SrpmCopyCommand, self).__init__(srpm_copy, name='srpm', description=DESC_SRPM)


class DrpmCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def drpm_copy(**kwargs):
            return _copy(self.context, TYPE_ID_DRPM, **kwargs)
        super(DrpmCopyCommand, self).__init__(drpm_copy, name='drpm', description=DESC_DRPM)
        

class ErrataCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def errata_copy(**kwargs):
            return _copy(self.context, TYPE_ID_ERRATA, **kwargs)
        super(ErrataCopyCommand, self).__init__(errata_copy, name='errata', description=DESC_ERRATA)
        self.add_option(COPY_CHILD_RPMS_OPTION)


class DistributionCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def distribution_copy(**kwargs):
            return _copy(self.context, TYPE_ID_DISTRO, **kwargs)
        super(DistributionCopyCommand, self).__init__(distribution_copy, name='distribution', description=DESC_DISTRIBUTION)


class PackageGroupCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def package_group_copy(**kwargs):
            return _copy(self.context, TYPE_ID_PKG_GROUP, **kwargs)
        super(PackageGroupCopyCommand, self).__init__(package_group_copy, name='group', description=DESC_PKG_GROUP)
        self.add_option(COPY_CHILD_RPMS_OPTION)


class PackageCategoryCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        self.context = context
        def package_category_copy(**kwargs):
            return _copy(self.context, TYPE_ID_PKG_CATEGORY, **kwargs)
        super(PackageCategoryCopyCommand, self).__init__(package_category_copy, name='category', description=DESC_PKG_CATEGORY)
        self.add_option(COPY_CHILD_GROUPS_OPTION)


def _copy(context, type_id, **kwargs):
    """
    This is a generic command that will perform a search for any type of
    content and copy it from one repository to another

    :param type_id: type of unit being copied
    :type  type_id: str

    :param kwargs:  CLI options as input by the user and passed in by
                    okaara. These are search options defined elsewhere that
                    also
    :type  kwargs:  dict
    """
    from_repo = kwargs['from-repo-id']
    to_repo = kwargs['to-repo-id']
    kwargs['type_ids'] = [type_id]
    # pass a custom override_config if this option is present
    if COPY_CHILD_RPMS_OPTION.keyword in kwargs:
        kwargs['override_config'] = {constants.CONFIG_COPY_CHILDREN: kwargs[COPY_CHILD_RPMS_OPTION.keyword]}
        del kwargs[COPY_CHILD_RPMS_OPTION.keyword]

    # If rejected an exception will bubble up and be handled by middleware.
    # The only caveat is if the source repo ID is invalid, it will come back
    # from the server as source_repo_id. The client-side name for this value
    # is from-repo-id, so do a quick substitution in the exception and then
    # reraise it for the middleware to handle like normal.
    try:
        response = context.server.repo_unit.copy(from_repo, to_repo, **kwargs)
    except BadRequestException, e:
        if 'source_repo_id' in e.extra_data.get('property_names', []):
            e.extra_data['property_names'].remove('source_repo_id')
            e.extra_data['property_names'].append('from-repo-id')
        raise e, None, sys.exc_info()[2]

    progress_msg = _('Progress on this task can be viewed using the '
                     'commands under "repo tasks".')

    if response.response_body.is_postponed():
        d = _('Unit copy postponed due to another operation on the destination '
              'repository.')
        d += progress_msg
        context.prompt.render_paragraph(d)
        context.prompt.render_reasons(response.response_body.reasons)
    else:
        context.prompt.render_paragraph(progress_msg)
