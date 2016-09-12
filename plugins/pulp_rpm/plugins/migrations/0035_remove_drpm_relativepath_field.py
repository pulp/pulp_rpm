"""
Migration to remove the `relativepath` field from DRPM units,
that are no longer used.
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
    units_drpm_collection = db['units_drpm']
    units_drpm_collection.update(
        {'relativepath': {'$exists': True}},
        {'$unset': {'relativepath': True}},
        multi=True
    )
