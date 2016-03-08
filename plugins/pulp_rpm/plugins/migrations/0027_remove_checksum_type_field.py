"""
This migration removes the `checksum_type` field of the units_rpm collection.
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
    collection = db['units_rpm']
    collection.update(
        {"checksum_type": {"$exists": True}},
        {"$unset": {"checksum_type": True}},
        multi=True)
