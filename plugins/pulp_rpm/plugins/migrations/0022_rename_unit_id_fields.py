"""
This migration renames `id` fields of each unit collection to
something more specificof the units collections to something
more specific. This works around mongoengines inability to
have a _id and id field on a document.
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

    migrate_id('units_distribution', 'distribution_id')
    migrate_id('units_erratum', 'errata_id')
    migrate_id('units_package_group', 'package_group_id')
    migrate_id('units_package_category', 'package_category_id')
    migrate_id('units_package_environment', 'package_environment_id')


def migrate_id(collection, new_field_name):
    """
    Migrate a given collection

    Drop all indexes in the collection containing the 'id' field
    and rename the id field to a new name

    :param collection: the name of the collection to migrate
    :type collection: str
    :param new_field_name: The new name for the 'id' field
    :type new_field_name: str
    """
    collection = connection.get_collection(collection)
    # Drop any index containing an id
    index_info = collection.index_information()
    indexes_to_drop = []
    for index_name, index_details in index_info.iteritems():
        for index_key in index_details['key']:
            if index_key[0] == 'id':
                indexes_to_drop.append(index_name)

    for index in indexes_to_drop:
        collection.drop_index(index)

    # Rename the id
    collection.update({}, {'$rename': {'id': new_field_name}})
