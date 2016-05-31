"""
Migration to remove the `_rpm_references` field from Errata units, which is no
longer used.
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
    units_erratum_collection = db['units_erratum']
    units_erratum_collection.update(
        {'_rpm_references': {'$exists': True}},
        {'$unset': {'_rpm_references': True}},
        multi=True
    )
