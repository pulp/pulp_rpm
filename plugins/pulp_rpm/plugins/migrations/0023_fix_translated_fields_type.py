"""
This migration modifies translated_name and translated_description.

When translated_name or translated_description are set to empty string, This migration sets them
to {}. This is required since empty string will not validate with the Mongoengine definition.
"""
from pulp.server.db import connection


def fix_translated_fields_string_to_dict(collection):
    """
    Change translated_name and translated_description fields to {} if they are "".

    :param collection: The collection to have its translated fields fixed up
    :type  collection: pymongo.Collection

    :rtype: None
    """
    collection.update({"translated_name": ""}, {'$set': {'translated_name': {}}}, multi=True)
    collection.update(
        {"translated_description": ""},
        {'$set': {'translated_description': {}}},
        multi=True
    )


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()

    fix_translated_fields_string_to_dict(db['units_package_category'])
    fix_translated_fields_string_to_dict(db['units_package_environment'])
    fix_translated_fields_string_to_dict(db['units_package_group'])
