from unittest import TestCase

from mock import Mock, patch

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0028_standard_storage_path'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(TestCase):
    """
    Test migration 0028.
    """
    @patch(PATH_TO_MODULE + '.iso_plan')
    @patch(PATH_TO_MODULE + '.yum_metadata_plan')
    @patch(PATH_TO_MODULE + '.distribution_plan')
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

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_distribution(self, get_collection):
        # test
        plan = migration.distribution_plan()

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

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_yum_metadata(self, get_collection):
        # test
        plan = migration.yum_metadata_plan()

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

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_iso(self, get_collection):
        # test
        plan = migration.iso_plan()

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
