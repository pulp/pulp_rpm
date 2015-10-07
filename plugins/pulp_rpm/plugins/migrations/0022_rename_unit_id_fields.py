"""
This migration renames fields that are renamed due to required changes
as part of the switch to mongoengine.
"""
from pulp.server.db import connection
from pymongo.errors import OperationFailure


def _drop_and_silence_exception(collection, index_name):
    try:
        collection.drop_index(index_name)
    except OperationFailure:
        # The index is already dropped
        pass


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()

    collection = db['units_distribution']
    collection.update({}, {"$rename": {"id": "distribution_id"}})
    _drop_and_silence_exception(collection, 'id_1')
    _drop_and_silence_exception(collection, 'id_1_family_1_variant_1_version_1_arch_1')

    collection = db['units_erratum']
    collection.update({}, {"$rename": {"id": "errata_id"}})
    collection.update({}, {"$rename": {"from": "errata_from"}})
    _drop_and_silence_exception(collection, 'id_1')

    collection = db['units_package_group']
    collection.update({}, {"$rename": {"id": "package_group_id"}})
    _drop_and_silence_exception(collection, 'id_1')
    _drop_and_silence_exception(collection, 'id_1_repo_id_1')

    collection = db['units_package_category']
    collection.update({}, {"$rename": {"id": "package_category_id"}})
    _drop_and_silence_exception(collection, 'id_1')
    _drop_and_silence_exception(collection, 'id_1_repo_id_1')

    collection = db['units_package_environment']
    collection.update({}, {"$rename": {"id": "package_environment_id"}})
    _drop_and_silence_exception(collection, 'id_1')
    _drop_and_silence_exception(collection, 'id_1_repo_id_1')
