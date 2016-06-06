"""
Migration to remove the `filelist` and `_erratum_references` fields from RPM units,
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
    units_rpm_collection = db['units_rpm']
    units_rpm_collection.update(
        {'filelist': {'$exists': True}},
        {'$unset': {'filelist': True}},
        multi=True
    )
    units_rpm_collection.update(
        {'_erratum_references': {'$exists': True}},
        {'$unset': {'_erratum_references': True}},
        multi=True
    )
