from pulp.server.db import connection

from pulp.plugins.migration.standard_storage_path import Migration, Plan


def migrate(*args, **kwargs):
    """
    Migrate content units to use the standard storage path introduced in pulp 2.8.
    """
    migration = Migration()
    migration.add(rpm_plan())
    migration.add(srpm_plan())
    migration.add(drpm_plan())
    migration.add(distribution_plan())
    migration.add(yum_metadata_plan())
    migration.add(iso_plan())
    migration()


def package_plan(collection):
    """
    Factory to create a package migration plan.

    :param collection: A package collection.
    :type collection: pymongo.collection.Collection
    :return: A configured plan.
    :rtype: Plan
    """
    key_fields = (
        'name',
        'epoch',
        'version',
        'release',
        'arch',
        'checksumtype',
        'checksum'
    )
    return Plan(collection, key_fields)


def rpm_plan():
    """
    Factory to create an RPM migration plan.

    :return: A configured plan.
    :rtype: Plan
    """
    collection = connection.get_collection('units_rpm')
    return package_plan(collection)


def srpm_plan():
    """
    Factory to create an SRPM migration plan.

    :return: A configured plan.
    :rtype: Plan
    """
    collection = connection.get_collection('units_srpm')
    return package_plan(collection)


def drpm_plan():
    """
    Factory to create an DRPM migration plan.

    :return: A configured plan.
    :rtype: Plan
    """
    key_fields = (
        'epoch',
        'version',
        'release',
        'filename',
        'checksumtype',
        'checksum'
    )
    collection = connection.get_collection('units_drpm')
    return Plan(collection, key_fields)


def distribution_plan():
    """
    Factory to create an Distribution migration plan.

    :return: A configured plan.
    :rtype: Plan
    """
    key_fields = (
        'distribution_id',
        'family',
        'variant',
        'version',
        'arch'
    )
    collection = connection.get_collection('units_distribution')
    return Plan(collection, key_fields, join_leaf=False)


def yum_metadata_plan():
    """
    Factory to create an YUM metadata migration plan.

    :return: A configured plan.
    :rtype: Plan
    """
    key_fields = (
        'data_type',
        'repo_id'
    )
    collection = connection.get_collection('units_yum_repo_metadata_file')
    return Plan(collection, key_fields)


def iso_plan():
    """
    Factory to create an ISO migration plan.

    :return: A configured plan.
    :rtype: Plan
    """
    key_fields = (
        'name',
        'checksum',
        'size'
    )
    collection = connection.get_collection('units_iso')
    return Plan(collection, key_fields)
