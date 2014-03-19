# -*- coding: utf-8 -*-

"""
Adds encoded sorting indexes for version and release to RPMs, SRPMs, and DRPMs that do not
already have them.
"""

from pulp.plugins.types import database as types_db

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM)
from pulp_rpm.common import version_utils


def migrate(*args, **kwargs):
    for type_id in (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM):
        _update_type(type_id)


def _update_type(type_id):
    collection = types_db.type_units_collection(type_id)

    # Both indexes should be set at the same time, so this single check should be safe
    fix_us = collection.find({'version_sort_index' : None})
    for package in fix_us:
        package['version_sort_index'] = version_utils.encode(package['version'])
        package['release_sort_index'] = version_utils.encode(package['release'])

        collection.save(package, safe=True)
