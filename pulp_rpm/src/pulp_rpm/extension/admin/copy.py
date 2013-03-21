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
from pulp.client.commands.unit import UnitCopyCommand
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY

# -- constants ----------------------------------------------------------------

DESC_RPM = _('copy RPMs from one repository to another')
DESC_SRPM = _('copy SRPMs from one repository to another')
DESC_DRPM = _('copy DRPMs from one repository to another')
DESC_ERRATA = _('copy errata from one repository to another')
DESC_DISTRIBUTION = _('copy distributions from one repository to another')
DESC_PKG_GROUP = _('copy package groups from one repository to another')
DESC_PKG_CATEGORY = _('copy package categories from one repository to another')


# -- commands -----------------------------------------------------------------

class RpmCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def rpm_copy(**kwargs):
            return _copy(self.context, TYPE_ID_RPM, **kwargs)
        super(RpmCopyCommand, self).__init__(context, name='rpm', description=DESC_RPM, method=rpm_copy)


class SrpmCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def srpm_copy(**kwargs):
            return _copy(self.context, TYPE_ID_SRPM, **kwargs)
        super(SrpmCopyCommand, self).__init__(context, name='srpm', description=DESC_SRPM, method=srpm_copy)


class DrpmCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def drpm_copy(**kwargs):
            return _copy(self.context, TYPE_ID_DRPM, **kwargs)
        super(DrpmCopyCommand, self).__init__(context, name='drpm', description=DESC_DRPM, method=drpm_copy)
        

class ErrataCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def errata_copy(**kwargs):
            return _copy(self.context, TYPE_ID_ERRATA, **kwargs)
        super(ErrataCopyCommand, self).__init__(context, name='errata', description=DESC_ERRATA, method=errata_copy)


class DistributionCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def distribution_copy(**kwargs):
            return _copy(self.context, TYPE_ID_DISTRO, **kwargs)
        super(DistributionCopyCommand, self).__init__(context, name='distribution', description=DESC_DISTRIBUTION, method=distribution_copy)


class PackageGroupCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def package_group_copy(**kwargs):
            return _copy(self.context, TYPE_ID_PKG_GROUP, **kwargs)
        super(PackageGroupCopyCommand, self).__init__(context, name='group', description=DESC_PKG_GROUP, method=package_group_copy)


class PackageCategoryCopyCommand(UnitCopyCommand):

    def __init__(self, context):
        def package_category_copy(**kwargs):
            return _copy(self.context, TYPE_ID_PKG_CATEGORY, **kwargs)
        super(PackageCategoryCopyCommand, self).__init__(context, name='category', description=DESC_PKG_CATEGORY, method=package_category_copy)


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
