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
    migration.add(yum_metadata_plan())
    migration.add(Distribution())
    migration.add(ISO())
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


class Distribution(Plan):
    """
    The migration plan for Distribution units.
    """

    def __init__(self):
        """
        Call super with collection and fields.
        """
        key_fields = (
            'distribution_id',
            'family',
            'variant',
            'version',
            'arch'
        )
        collection = connection.get_collection('units_distribution')
        super(Distribution, self).__init__(collection, key_fields, join_leaf=False)

    def _new_path(self, unit):
        """
        The *variant* might not exist in the document for older units.
        Default the variant part of the unit key to '' which matches the model.

        :param unit: The unit being migrated.
        :type  unit: pulp.plugins.migration.standard_storage_path.Unit
        :return: The new path.
        :rtype: str
        """
        unit.document.setdefault('variant', '')
        return super(Distribution, self)._new_path(unit)


class ISO(Plan):
    """
    The migration plan for ISO units.
    """

    def __init__(self):
        """
        Call super with collection and fields.
        """
        key_fields = (
            'name',
            'checksum',
            'size'
        )
        collection = connection.get_collection('units_iso')
        super(ISO, self).__init__(collection, key_fields)

    def _new_path(self, unit):
        """
        Units created by 2.8.0 don't include the ISO name.  This was a regression
        that is being corrected by this additional logic.  If the storage path
        does not end with the *name* stored in the unit, it is appended.

        :param unit: The unit being migrated.
        :type  unit: pulp.plugins.migration.standard_storage_path.Unit
        :return: The new path.
        :rtype: str
        """
        name = unit.document['name']
        path = unit.document['_storage_path']
        if not path.endswith(name):
            unit.document['_storage_path'] = name
        new_path = super(ISO, self)._new_path(unit)
        return new_path
