"""
Migration to remove the `checksum_type` field from SRPM/DRPM units,
that is no longer used.
"""

from pulp.server.db import connection


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    units_srpm_collection = db['units_srpm']
    units_drpm_collection = db['units_drpm']
    units_srpm_collection.update(
        {'checksum_type': {'$exists': True}},
        {'$unset': {'checksum_type': True}},
        multi=True
    )
    units_drpm_collection.update(
        {'checksum_type': {'$exists': True}},
        {'$unset': {'checksum_type': True}},
        multi=True
    )
