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

import itertools
import logging

from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import models

_LOGGER = logging.getLogger(__name__)

STEP = 1000


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
        fields = model.UNIT_KEY_NAMES

        unit_keys_generator = (unit._asdict() for unit in values.copy())
        for unit in get_existing_units(unit_keys_generator, fields, unit_type, sync_conduit.get_units):
            named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
            values.discard(named_tuple)

    ret = set()
    ret.update(*sorted_units.values())
    return ret


def get_existing_units(search_dicts, unit_fields, unit_type, search_method):
    for segment in _paginate(search_dicts, STEP):
        unit_filters = {'$or': list(segment)}
        criteria = UnitAssociationCriteria([unit_type], unit_filters=unit_filters,
                                           unit_fields=unit_fields, association_fields=[])
        for result in search_method(criteria):
            yield result


def _sort_by_type(wanted):
    ret = {}
    for unit in wanted:
        unit_type = unit.__class__.__name__
        ret.setdefault(unit_type, set()).add(unit)
    return ret


def _paginate(iterable, page_size):
    i = 0
    while True:
        page = list(itertools.islice(iterable, i, i+page_size))
        if not page:
            return
        i = i + page_size
        yield page
