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

import logging

from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.utils import paginate


_LOGGER = logging.getLogger(__name__)


def check_repo(wanted, unit_search_method):
    """
    Given an iterable of units as namedtuples, this function will search for them
    using the given search method and return the set of tuples that were not
    found.

    This is useful in a case where you know what units you want to have in a repo,
    but need to know which you need to actually download by eliminating the ones
    you already have.

    :param wanted:          iterable of units as namedtuples
    :type  wanted:          iterable
    :param sync_conduit:
    :type  sync_conduit:    pulp.plugins.conduits.repo_sync.RepoSyncConduit

    :return:    set of unit keys as namedtuples, identifying which of the
                named tuples received as input were not found by the
                search method.
    :rtype:     set
    """
    # sort by type
    sorted_units = _sort_by_type(wanted)
    # UAQ for each type
    for unit_type, values in sorted_units.iteritems():
        model = models.TYPE_MAP[unit_type]
        fields = model.UNIT_KEY_NAMES

        unit_keys_generator = (unit._asdict() for unit in values.copy())
        for unit in get_existing_units(unit_keys_generator, fields, unit_type, unit_search_method):
            named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
            values.discard(named_tuple)

    ret = set()
    ret.update(*sorted_units.values())
    return ret


def get_existing_units(search_dicts, unit_fields, unit_type, search_method):
    """

    :param search_dicts:
    :param unit_fields:
    :param unit_type:
    :param search_method:
    :return:    generator of Units
    """
    for segment in paginate(search_dicts):
        unit_filters = {'$or': list(segment)}
        criteria = UnitAssociationCriteria([unit_type], unit_filters=unit_filters,
                                           unit_fields=unit_fields, association_fields=[])
        for result in search_method(criteria):
            yield result


def _sort_by_type(wanted):
    ret = {}
    for unit in wanted:
        ret.setdefault(unit.__class__.__name__, set()).add(unit)
    return ret
