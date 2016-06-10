import os

from unittest import TestCase

from mock import Mock, patch

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0028_standard_storage_path'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(TestCase):
    """
    Test migration 0028.
    """
    @patch(PATH_TO_MODULE + '.ISO')
    @patch(PATH_TO_MODULE + '.Distribution')
    @patch(PATH_TO_MODULE + '.YumMetadataFile')
    @patch(PATH_TO_MODULE + '.drpm_plan')
    @patch(PATH_TO_MODULE + '.srpm_plan')
    @patch(PATH_TO_MODULE + '.rpm_plan')
    @patch(PATH_TO_MODULE + '.Migration')
    def test_migrate(self, _migration, *functions):
        plans = []
        _migration.return_value.add.side_effect = plans.append

        # test
        migration.migrate()

        # validation
        self.assertEqual(
            plans,
            [
                f.return_value for f in functions
            ])
        _migration.return_value.assert_called_once_with()


class TestPlans(TestCase):

    def test_package(self):
        collection = Mock()

        # test
        plan = migration.package_plan(collection)

        # validation
        self.assertEqual(plan.collection, collection)
        self.assertEqual(
            plan.key_fields,
            (
                'name',
                'epoch',
                'version',
                'release',
                'arch',
                'checksumtype',
                'checksum'
            ))
        self.assertTrue(plan.join_leaf)
        self.assertTrue(isinstance(plan, migration.Plan))

    @patch(PATH_TO_MODULE + '.package_plan')
    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_rpm(self, get_collection, package_plan):
        # test
        plan = migration.rpm_plan()

        # validation
        get_collection.assert_called_once_with('units_rpm')
        package_plan.assert_called_once_with(get_collection.return_value)
        self.assertEqual(plan, package_plan.return_value)

    @patch(PATH_TO_MODULE + '.package_plan')
    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_srpm(self, get_collection, package_plan):
        # test
        plan = migration.srpm_plan()

        # validation
        get_collection.assert_called_once_with('units_srpm')
        package_plan.assert_called_once_with(get_collection.return_value)
        self.assertEqual(plan, package_plan.return_value)

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_drpm(self, get_collection):
        # test
        plan = migration.drpm_plan()

        # validation
        get_collection.assert_called_once_with('units_drpm')
        self.assertEqual(plan.collection, get_collection.return_value)
        self.assertEqual(
            plan.key_fields,
            (
                'epoch',
                'version',
                'release',
                'filename',
                'checksumtype',
                'checksum'
            ))
        self.assertTrue(plan.join_leaf)
        self.assertTrue(isinstance(plan, migration.Plan))


class TestISO(TestCase):

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_init(self, get_collection):
        # test
        plan = migration.ISO()

        # validation
        get_collection.assert_called_once_with('units_iso')
        self.assertEqual(plan.collection, get_collection.return_value)
        self.assertEqual(
            plan.key_fields,
            (
                'name',
                'checksum',
                'size'
            ))
        self.assertTrue(plan.join_leaf)
        self.assertTrue(isinstance(plan, migration.Plan))

    @patch(PATH_TO_MODULE + '.Plan._new_path')
    @patch(PATH_TO_MODULE + '.connection.get_collection', Mock())
    def test_new_path(self, new_path):
        name = 'rhel.iso'
        unit = Mock(
            document={
                '_storage_path': 'something',
                'name': name
            })

        def _new_path(u):
            return os.path.join('1234', u.document['_storage_path'])

        new_path.side_effect = _new_path

        # test
        plan = migration.ISO()
        path = plan._new_path(unit)

        # validation
        self.assertEqual(path, os.path.join('1234', name))


class TestDistribution(TestCase):

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_init(self, get_collection):
        # test
        plan = migration.Distribution()

        # validation
        get_collection.assert_called_once_with('units_distribution')
        self.assertEqual(plan.collection, get_collection.return_value)
        self.assertEqual(
            plan.key_fields,
            (
                'distribution_id',
                'family',
                'variant',
                'version',
                'arch'
            ))
        self.assertFalse(plan.join_leaf)
        self.assertTrue(isinstance(plan, migration.Plan))

    @patch(PATH_TO_MODULE + '.Plan._new_path')
    @patch(PATH_TO_MODULE + '.connection.get_collection', Mock())
    def test_new_path(self, new_path):
        variant = 1234
        unit = Mock(document={'variant': variant})

        # test
        plan = migration.Distribution()
        path = plan._new_path(unit)

        # validation
        self.assertEqual(unit.document['variant'], variant)
        self.assertEqual(path, new_path.return_value)

    @patch(PATH_TO_MODULE + '.Plan._new_path')
    @patch(PATH_TO_MODULE + '.connection.get_collection', Mock())
    def test_new_path_without_variant(self, new_path):
        unit = Mock(document={})

        # test
        plan = migration.Distribution()
        path = plan._new_path(unit)

        # validation
        self.assertEqual(unit.document['variant'], '')
        self.assertEqual(path, new_path.return_value)


class TestYumMetadataFile(TestCase):

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_init(self, get_collection):
        # test
        plan = migration.YumMetadataFile()

        # validation
        get_collection.assert_called_once_with('units_yum_repo_metadata_file')
        self.assertEqual(plan.collection, get_collection.return_value)
        self.assertEqual(
            plan.key_fields,
            (
                'data_type',
                'repo_id'
            ))
        self.assertTrue(plan.join_leaf)
        self.assertTrue(isinstance(plan, migration.Plan))

    @patch(PATH_TO_MODULE + '.shutil')
    @patch(PATH_TO_MODULE + '.mkdir')
    @patch(PATH_TO_MODULE + '.connection.get_collection', Mock())
    @patch('os.path.exists')
    def test_migrate(self, path_exists, mkdir, shutil):
        unit_id = '123'
        path = '/tmp/old/path_1'
        new_path = '/tmp/new/content/path_2'
        path_exists.return_value = True

        # test
        plan = migration.YumMetadataFile()
        plan.migrate(unit_id, path, new_path)

        # validation
        path_exists.assert_called_once_with(path)
        mkdir.assert_called_once_with(os.path.dirname(new_path))
        shutil.copy.assert_called_once_with(path, new_path)
        plan.collection.update_one.assert_called_once_with(
            filter={'_id': unit_id},
            update={'$set': {'_storage_path': new_path}})
