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

from pulp.server.db.model.criteria import Criteria

_LOGGER = logging.getLogger(__name__)

STEP = 1000

def sort_tuples_by_type(unit_keys_with_type):
    types = {}
    #expected_num_fields = len(unit_key_field_names) + 1
    for unit_key_values in unit_keys_with_type:
        #if len(unit_key_values) != expected_num_fields:
            #raise ValueError('wrong number of values for unit key')

        types.setdefault(unit_key_values[0], []).append(unit_keys_with_type)
    return types


def sort_dicts_by_type(unit_keys):
    types = {}
    for unit_key in unit_keys:
        unit_key_copy = unit_key.copy()
        type_id = unit_key_copy.pop('type_id')
        types[type_id] = unit_key_copy
    return types


def determine_needed_packages(unit_keys_with_type, unit_key_names, sync_conduit):
    ret = []
    start = 0
    type_id = unit_keys_with_type[0][0]
    while True:
        units = unit_keys_with_type[start:start+STEP]
        if not units:
            break
        start += STEP

        filters = {'$or': (_unit_key_tuple_to_dict(unit, unit_key_names) for unit in units)}
        criteria = Criteria(fields=unit_key_names, filters=filters)
        matches = sync_conduit.search_all_units(type_id, criteria)


def _unit_key_tuple_to_dict(unit_key_with_type, unit_key_names):
    ret = {}
    for i, unit_key_value in enumerate(unit_key_with_type[1:]):
        ret[unit_key_names[i]] = unit_key_value

    return ret


def _unit_key_dict_to_tuple(unit_key, type_id):
    return


def filter_associations_and_downloads(sync_conduit, unit_keys_with_type):
    unit_keys_by_type = sort_dicts_by_type(unit_keys_with_type)
    for type_id in unit_keys_by_type:
        # search repo for these units
        pass

    # for units not in repo, search whole system

    # return units to associate and units to download

    return [], []