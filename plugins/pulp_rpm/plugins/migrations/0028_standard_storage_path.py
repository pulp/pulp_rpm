import logging
import os
import shutil

from pulp.server.db import connection

from pulp.plugins.migration.standard_storage_path import Migration, Plan, Unit
from pulp.plugins.util.misc import mkdir


_logger = logging.getLogger(__name__)


def migrate(*args, **kwargs):
    """
    Migrate content units to use the standard storage path introduced in pulp 2.8.
    """
    msg = '* NOTE: This migration may take a long time depending on the size of your Pulp content *'
    stars = '*' * len(msg)

    _logger.info(stars)
    _logger.info(msg)
    _logger.info(stars)

    migration = Migration()
    migration.add(rpm_plan())
    migration.add(srpm_plan())
    migration.add(drpm_plan())
    migration.add(YumMetadataFile())
    migration.add(DistributionPlan())
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


class DistributionPlan(Plan):
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
        super(DistributionPlan, self).__init__(collection, key_fields, join_leaf=False)
        self.fields.add('files')

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
        return super(DistributionPlan, self)._new_path(unit)

    def _new_unit(self, document):
        """
        Create a new distribution unit for the specified document.

        :param document: A content unit document fetched from the DB.
        :type document: dict
        :return: A new unit.
        :rtype: DistributionUnit
        """
        return DistributionUnit(self, document)


class DistributionUnit(Unit):
    """
    Specialized distribution unit.
    """

    @property
    def files(self):
        """
        List of files (relative paths) associated with the unit.
        """
        files = [
            'treeinfo',
            '.treeinfo'
        ]
        files.extend([f['relativepath'] for f in self.document['files']])
        return files


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


class YumMetadataFile(Plan):
    """
    The migration plan for yum_repo_metadata_file units.
    """

    def __init__(self):
        """
        Call super with collection and fields.
        """
        key_fields = (
            'data_type',
            'repo_id'
        )
        collection = connection.get_collection('units_yum_repo_metadata_file')
        super(YumMetadataFile, self).__init__(collection, key_fields)

    def migrate(self, unit_id, path, new_path):
        """
        Migrate the unit.
          1. copy content
          2. update the DB
        :param unit_id: A unit UUID.
        :type unit_id: str
        :param path: The current storage path.
        :type path: str
        :param new_path: The new storage path.
        :type new_path: str
        """
        # the content should be copied(and not moved) due to this issue #1944
        if os.path.exists(path):
            mkdir(os.path.dirname(new_path))
            shutil.copy(path, new_path)
        self.collection.update_one(
            filter={
                '_id': unit_id
            },
            update={
                '$set': {'_storage_path': new_path}
            })
