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

from pulp.server.db.model.criteria import Criteria, UnitAssociationCriteria
from pulp_rpm.common import models

_LOGGER = logging.getLogger(__name__)

STEP = 1000


# TODO: delete this?
def main(wanted, sync_conduit):
    """

    :param wanted:          iterable of namedtuples representing unit keys
    :type  wanted:          iterable
    :type  sync_conduit:    pulp.plugins.conduits.repo_sync.RepoSyncConduit

    :return:    two sets of namedtuples representing unit keys: the first should
                be downloaded, the second should be associated with the repo
    :rtype:     (set, set)
    """
    sorted_needs = check_repo(wanted, sync_conduit)
    to_download, to_associate = check_system(sorted_needs, sync_conduit)
    return to_download, to_associate


def check_repo(wanted, sync_conduit):
    """

    :param wanted:          iterable of unit keys as namedtuples
    :type  wanted:          iterable
    :param sync_conduit:
    :type  sync_conduit:    pulp.plugins.conduits.repo_sync.RepoSyncConduit

    :return:    set of unit keys as namedtuples
    :rtype:     set
    """
    # sort by type
    sorted_units = _sort_by_type(wanted)
    # UAQ for each type
    for unit_type, values in sorted_units.iteritems():
        model = models.TYPE_MAP[unit_type]
        unit_filters = {'$or': [unit._asdict() for unit in values]}
        fields = model.UNIT_KEY_NAMES
        criteria = UnitAssociationCriteria([unit_type], unit_filters=unit_filters, unit_fields=fields, association_fields=[])
        results = sync_conduit.get_units(criteria)
        for unit in results:
            named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
            values.discard(named_tuple)

    ret = set()
    ret.update(*sorted_units.values())
    return ret


# TODO: delete this? Might not want to do this at all
def check_system(sorted_needs, sync_conduit):
    to_associate = set()
    # Criteria for each type
    for unit_type, values in sorted_needs.iteritems():
        if not values:
            # can happen if all units of a type get eliminated by check_repo
            continue
        model = models.TYPE_MAP[unit_type]
        fields = model.UNIT_KEY_NAMES
        filters = {'$or': [unit._asdict() for unit in values]}
        criteria = Criteria(filters =filters, fields=fields)
        results = sync_conduit.search_all_units(unit_type, criteria)
        for unit in results:
            model_instance = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
            values.discard(model_instance)
            to_associate.add(unit)
    to_download = set()
    to_download.update(*sorted_needs.values())
    return to_download, to_associate


def _sort_by_type(wanted):
    ret = {}
    for unit in wanted:
        unit_type = unit.__class__.__name__
        ret.setdefault(unit_type, set()).add(unit)
    return ret
