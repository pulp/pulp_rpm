"""
Migration to ensure all distribution units have the variant field.
"""

from pulp.server.db import connection


def migrate(*args, **kwargs):
    """
    Migration to ensure all distribution units have the variant field.
    Defaulting to '' matches the model.

    :param args: unused
    :type  args: tuple
    :param kwargs: unused
    :type  kwargs: dict
    """
    variant = 'variant'
    collection = connection.get_collection('units_distribution')
    collection.update(
        {'$or': [
            {variant: None},
            {variant: {'$exists': False}}
        ]},
        {'$set': {variant: ''}}, multi=True)
