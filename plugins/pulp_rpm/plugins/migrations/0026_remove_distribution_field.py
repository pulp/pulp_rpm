"""
Migration to remove the pulp_distribution_xml_file field from Distribution units, which is no
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
    units_distribution_collection = db['units_distribution']
    units_distribution_collection.update(
        {'pulp_distribution_xml_file': {'$exists': True}},
        {'$unset': {'pulp_distribution_xml_file': True}},
        multi=True
    )
