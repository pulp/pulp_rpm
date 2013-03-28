# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
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

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY)


def display_units(prompt, units, unit_threshold):
    """
    Used to display a list of units that were received from a server-side operation, such as
    associate or unassociate. This call will determine whether or not to display a list of each
    unit or simply summary information.

    The units parameter must be a list of dictionaries containing two keys: type_id and unit_key.
    The data returned from the server will likely be in this format already/

    :param units: list of unit IDs from the server
    :type  units: list
    :param unit_threshold: maximum number of units to display by name; if len(units) is greater than
           this, a summary with counts by type will be displayed instead
    :type  unit_threshold: int
    """

    if len(units) == 0:
        prompt.write(_('Nothing found that matches the given criteria.'), tag='too-few')

    elif len(units) >= unit_threshold:
        _summary(prompt, units)

    else:
        _details(prompt, units)

def _summary(prompt, units):
    """
    Displays a shortened view of the units. This implementation will display a count of units by type.
    """

    # Create count by each by type
    unit_count_by_type = {}
    for u in units:
        count = unit_count_by_type.setdefault(u['type_id'], 0)
        unit_count_by_type[u['type_id']] = count + 1

    msg = _('Summary:')
    prompt.write(msg, tag='summary')
    for type_id, count in unit_count_by_type.items():
        entry = '  %s: %s' % (type_id, count)
        prompt.write(entry, tag='count-entry')

def _details(prompt, units):
    """
    Displays information about each unit. If multiple types are present, the
    list will be broken down by type. As each unit is rendered, care should be taken to not call
    this with a large amount of units as it will flood the user's terminal.
    """

    # The unit keys will differ by type, so the formatting of a particular entry will have to be
    # handled on a type by type basis.
    type_formatters = {
        TYPE_ID_RPM : _details_package,
        TYPE_ID_SRPM : _details_package,
        TYPE_ID_DRPM : _details_drpm,
        TYPE_ID_ERRATA : _details_errata,
        TYPE_ID_DISTRO : _details_distribution,
        TYPE_ID_PKG_GROUP : _details_package_group,
        TYPE_ID_PKG_CATEGORY : _details_package_category,
    }

    # Restructure into a list of unit keys by type
    units_by_type = {}
    map(lambda u : units_by_type.setdefault(u['type_id'], []).append(u['unit_key']), units)

    # Each unit is formatted to accomodate its unit key and displayed
    prompt.write(_('Units:'), tag='header')

    sorted_type_ids = sorted(units_by_type.keys())
    for type_id in sorted_type_ids:
        unit_list = units_by_type[type_id]
        formatter = type_formatters[type_id]

        # Only display the type header if there's more than one type present
        if len(units_by_type) > 1:
            prompt.write(' %s:' % type_id, tag='type-header-%s' % type_id)

        # Preformat so we can apply the same alpha sort to each type instead of having a
        # custom comparator function per type
        formatted_units = map(lambda u : formatter(u), unit_list)
        formatted_units.sort()
        for u in formatted_units:
            prompt.write('  %s' % u, tag='unit-entry-%s' % type_id)

def _details_package(package):
    return '%s-%s-%s-%s' % (package['name'], package['version'], package['release'], package['arch'])

def _details_drpm(drpm):
    return drpm['filename']

def _details_errata(errata):
    return errata['id']

def _details_distribution(distribution):
    return '%s-%s-%s' % (distribution['id'], distribution['version'], distribution['arch'])

def _details_package_group(group):
    return group['id']

def _details_package_category(category):
    return category['id']
