from cStringIO import StringIO
import unittest
import functools

import mock
from mock import ANY
from nectar.config import DownloaderConfig
from pulp.common.plugins import importer_constants
from pulp.plugins.conduits.repo_sync import RepoSyncConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.managers import factory as manager_factory

from pulp_rpm.common import ids
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import purge
from pulp_rpm.plugins.importers.yum.repomd import metadata, primary, presto, updateinfo, group
import model_factory


manager_factory.initialize()


class TestPurgeBase(unittest.TestCase):
    def setUp(self):
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org', '/a/b/c',
                                                     DownloaderConfig())
        self.repo = Repository('repo1')
        self.config = PluginCallConfiguration({}, {})
        self.conduit = RepoSyncConduit(self.repo.id, 'yum_importer')


class TestRemoveMissing(TestPurgeBase):
    @skip_broken
    @mock.patch.object(purge, 'get_existing_units', autospec=True)
    def test_remove_missing_units(self, mock_get_existing):
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)
        # setup such that only one of the 2 existing units appears to be present
        # in the remote repo, thus the other unit should be purged
        mock_get_existing.return_value = model_factory.rpm_units(2)
        remote_named_tuples = set(model.as_named_tuple for model in model_factory.rpm_models(2))
        common_unit = mock_get_existing.return_value[1]
        common_named_tuple = models.RPM.NAMEDTUPLE(**common_unit.unit_key)
        remote_named_tuples.add(common_named_tuple)

        purge.remove_missing_units(self.conduit, models.RPM, remote_named_tuples)

        mock_get_existing.assert_called_once_with(models.RPM, self.conduit.get_units)
        self.conduit.remove_unit.assert_called_once_with(mock_get_existing.return_value[0])

    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    @mock.patch.object(purge, 'remove_missing_units', autospec=True)
    def test_remove_missing_rpms(self, mock_remove, mock_get_remote_units):
        purge.remove_missing_rpms(self.metadata_files, self.conduit)

        mock_get_remote_units.assert_called_once_with(ANY,
                                                      primary.PACKAGE_TAG,
                                                      primary.process_package_element)
        mock_remove.assert_called_once_with(self.conduit,
                                            models.RPM, mock_get_remote_units.return_value)

    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    @mock.patch.object(purge, 'remove_missing_units', autospec=True)
    def test_remove_missing_drpms(self, mock_remove, mock_get_remote_units):
        """
        Test that the purge makes the appropriate calls and that it calls
        for both of the prestodelta files
        """
        purge.remove_missing_drpms(self.metadata_files, self.conduit)

        mock_get_remote_units.assert_called_with(ANY, presto.PACKAGE_TAG,
                                                 presto.process_package_element)
        self.assertEquals(2, mock_get_remote_units.call_count)
        mock_remove.assert_called_once_with(self.conduit, models.DRPM, set())

    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    @mock.patch.object(purge, 'remove_missing_units', autospec=True)
    def test_remove_missing_errata(self, mock_remove, mock_get_remote_units):
        purge.remove_missing_errata(self.metadata_files, self.conduit)

        mock_get_remote_units.assert_called_once_with(ANY,
                                                      updateinfo.PACKAGE_TAG,
                                                      updateinfo.process_package_element)
        mock_remove.assert_called_once_with(self.conduit,
                                            models.Errata, mock_get_remote_units.return_value)

    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    @mock.patch.object(purge, 'remove_missing_units', autospec=True)
    def test_remove_missing_groups(self, mock_remove, mock_get_remote_units):
        purge.remove_missing_groups(self.metadata_files, self.conduit)

        mock_get_remote_units.assert_called_once_with(ANY, group.GROUP_TAG, ANY)
        mock_remove.assert_called_once_with(self.conduit,
                                            models.PackageGroup, mock_get_remote_units.return_value)

    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    @mock.patch.object(purge, 'remove_missing_units', autospec=True)
    def test_remove_missing_categories(self, mock_remove, mock_get_remote_units):
        purge.remove_missing_categories(self.metadata_files, self.conduit)

        mock_get_remote_units.assert_called_once_with(ANY, group.CATEGORY_TAG, ANY)
        mock_remove.assert_called_once_with(self.conduit,
                                            models.PackageCategory,
                                            mock_get_remote_units.return_value)

    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    @mock.patch.object(purge, 'remove_missing_units', autospec=True)
    def test_remove_missing_environments(self, mock_remove, mock_get_remote_units):
        purge.remove_missing_environments(self.metadata_files, self.conduit)

        mock_get_remote_units.assert_called_once_with(ANY, group.ENVIRONMENT_TAG, ANY)
        mock_remove.assert_called_once_with(self.conduit,
                                            models.PackageEnvironment,
                                            mock_get_remote_units.return_value)


class TestGetExistingUnits(TestPurgeBase):
    @skip_broken
    def test_get_existing_units(self):
        mock_search_func = mock.MagicMock(spec_set=self.conduit.get_units)

        purge.get_existing_units(models.RPM, mock_search_func)

        self.assertEqual(len(mock_search_func.call_args[0]), 1)
        # no kwargs
        self.assertEqual(len(mock_search_func.call_args[1]), 0)
        criteria = mock_search_func.call_args[0][0]
        self.assertTrue(isinstance(criteria, UnitAssociationCriteria))
        # ensure the correct type was set on the criteria
        self.assertEqual(criteria.type_ids, [models.RPM.TYPE])
        # limit the query to keys in the unit key, to conserve RAM
        self.assertEqual(criteria.unit_fields, models.RPM.UNIT_KEY_NAMES)


class TestGetRemoteUnits(TestPurgeBase):
    FAKE_TYPE = 'fake_type'

    def setUp(self):
        super(TestGetRemoteUnits, self).setUp()
        self.metadata_files.metadata[self.FAKE_TYPE] = {'local_path': '/a/b/c'}

    def test_no_units(self):
        file_function = mock.Mock(return_value=None)
        ret = purge.get_remote_units(file_function, 'bar', lambda x: x)

        self.assertEqual(ret, set())

    @skip_broken
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    @mock.patch('__builtin__.open', autospec=True)
    def test_rpm(self, mock_open, mock_package_list_generator):
        rpms = model_factory.rpm_models(2)
        mock_package_list_generator.return_value = rpms
        fake_file = StringIO()
        mock_open.return_value = fake_file

        def process_func(x):
            return x
        file_function = functools.partial(self.metadata_files.get_metadata_file_handle,
                                          self.FAKE_TYPE)
        ret = purge.get_remote_units(file_function, 'bar', process_func)

        mock_open.assert_called_once_with('/a/b/c', 'r')
        self.assertTrue(fake_file.closed)
        mock_package_list_generator.assert_called_once_with(fake_file, 'bar', process_func)
        self.assertEqual(len(rpms), len(ret))
        for model in rpms:
            self.assertTrue(model.as_named_tuple in ret)


class TestRemoveOldVersions(TestPurgeBase):
    def setUp(self):
        super(TestRemoveOldVersions, self).setUp()
        self.rpms = model_factory.rpm_models(3, True)
        self.rpms.extend(model_factory.rpm_models(2, False))
        self.srpms = model_factory.srpm_models(3, True)
        self.srpms.extend(model_factory.srpm_models(2, False))
        self.drpms = model_factory.drpm_models(3, True)
        self.drpms.extend(model_factory.drpm_models(2, False))

    @skip_broken
    def test_rpm_one(self):
        self.conduit.get_units = mock.MagicMock(
            spec_set=self.conduit.get_units,
            side_effect=lambda criteria: self.rpms if ids.TYPE_ID_RPM in criteria.type_ids else [])
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)

        purge.remove_old_versions(1, self.conduit)

        self.conduit.remove_unit.assert_any_call(self.rpms[0])
        self.conduit.remove_unit.assert_any_call(self.rpms[1])
        self.assertEqual(self.conduit.remove_unit.call_count, 2)

    @skip_broken
    def test_rpm_two(self):
        self.conduit.get_units = mock.MagicMock(
            spec_set=self.conduit.get_units,
            side_effect=lambda criteria: self.rpms if ids.TYPE_ID_RPM in criteria.type_ids else [])
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)

        purge.remove_old_versions(2, self.conduit)

        self.conduit.remove_unit.assert_called_once_with(self.rpms[0])

    @skip_broken
    def test_srpm_one(self):
        self.conduit.get_units = mock.MagicMock(
            spec_set=self.conduit.get_units,
            side_effect=lambda criteria: self.srpms if ids.TYPE_ID_SRPM in criteria.type_ids else []
        )
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)

        purge.remove_old_versions(1, self.conduit)

        self.conduit.remove_unit.assert_any_call(self.srpms[0])
        self.conduit.remove_unit.assert_any_call(self.srpms[1])
        self.assertEqual(self.conduit.remove_unit.call_count, 2)

    @skip_broken
    def test_srpm_two(self):
        self.conduit.get_units = mock.MagicMock(
            spec_set=self.conduit.get_units,
            side_effect=lambda criteria: self.srpms if ids.TYPE_ID_SRPM in criteria.type_ids else []
        )
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)

        purge.remove_old_versions(2, self.conduit)

        self.conduit.remove_unit.assert_called_once_with(self.srpms[0])

    @skip_broken
    def test_drpm_one(self):
        self.conduit.get_units = mock.MagicMock(
            spec_set=self.conduit.get_units,
            side_effect=lambda criteria: self.drpms if ids.TYPE_ID_DRPM in criteria.type_ids else []
        )
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)

        purge.remove_old_versions(1, self.conduit)

        self.conduit.remove_unit.assert_any_call(self.drpms[0])
        self.conduit.remove_unit.assert_any_call(self.drpms[1])
        self.assertEqual(self.conduit.remove_unit.call_count, 2)

    @skip_broken
    def test_drpm_two(self):
        self.conduit.get_units = mock.MagicMock(
            spec_set=self.conduit.get_units,
            side_effect=lambda criteria: self.drpms if ids.TYPE_ID_DRPM in criteria.type_ids else []
        )
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)

        purge.remove_old_versions(2, self.conduit)

        self.conduit.remove_unit.assert_called_once_with(self.drpms[0])


class TestPurgeUnwantedUnits(TestPurgeBase):
    @mock.patch.object(purge, 'get_remote_units', autospec=True)
    def test_remove_missing_false(self, mock_get_remote):
        self.config.plugin_config[importer_constants.KEY_UNITS_REMOVE_MISSING] = False

        purge.purge_unwanted_units(self.metadata_files, self.conduit, self.config)

        # this verifies that no attempt was made to remove missing units, since
        # nobody looked for missing units.
        self.assertEqual(mock_get_remote.call_count, 0)

    @mock.patch.object(purge, 'remove_missing_environments', autospec=True)
    @mock.patch.object(purge, 'remove_missing_rpms', autospec=True)
    @mock.patch.object(purge, 'remove_missing_drpms', autospec=True)
    @mock.patch.object(purge, 'remove_missing_errata', autospec=True)
    @mock.patch.object(purge, 'remove_missing_groups', autospec=True)
    @mock.patch.object(purge, 'remove_missing_categories', autospec=True)
    def test_remove_missing_true(self, mock_remove_categories, mock_remove_groups,
                                 mock_remove_errata, mock_remove_drpms, mock_remove_rpms,
                                 mock_remove_environments):
        self.config.plugin_config[importer_constants.KEY_UNITS_REMOVE_MISSING] = True

        purge.purge_unwanted_units(self.metadata_files, self.conduit, self.config)

        mock_remove_rpms.assert_called_once_with(self.metadata_files, self.conduit)
        mock_remove_drpms.assert_called_once_with(self.metadata_files, self.conduit)
        mock_remove_errata.assert_called_once_with(self.metadata_files, self.conduit)
        mock_remove_groups.assert_called_once_with(self.metadata_files, self.conduit)
        mock_remove_categories.assert_called_once_with(self.metadata_files, self.conduit)
        mock_remove_environments.assert_called_once_with(self.metadata_files, self.conduit)

    @mock.patch.object(purge, 'remove_old_versions', autospec=True)
    def test_retain_old_none(self, mock_remove_old_versions):
        self.config.plugin_config[importer_constants.KEY_UNITS_REMOVE_MISSING] = False

        purge.purge_unwanted_units(self.metadata_files, self.conduit, self.config)

        self.assertEqual(mock_remove_old_versions.call_count, 0)

    @mock.patch.object(purge, 'remove_old_versions', autospec=True)
    def test_retain_old(self, mock_remove_old_versions):
        self.config.plugin_config[importer_constants.KEY_UNITS_REMOVE_MISSING] = False
        self.config.plugin_config[importer_constants.KEY_UNITS_RETAIN_OLD_COUNT] = 2

        purge.purge_unwanted_units(self.metadata_files, self.conduit, self.config)

        mock_remove_old_versions.assert_called_once_with(3, self.conduit)


class RemoveUnitDuplicateNevra(TestPurgeBase):

    @skip_broken
    @mock.patch.object(purge, 'RepoUnitAssociationManager', autospec=True)
    @mock.patch.object(purge, 'UnitAssociationCriteria', autospec=True)
    def test_remove_unit_duplicate_nerva(self, mock_criteria, mock_association):
        unit_key = {'name': 'test-nevra', 'epoch': 0, 'version': 1, 'release': '23',
                    'arch': 'noarch', 'checksum': '1234abc', 'checksumtype': 'sha256'}
        type_id = 'rpm'
        repo_id = 'test-repo'
        expected_filters = set([('arch', 'noarch'), ('epoch', 0), ('name', 'test-nevra'),
                                ('release', '23'), ('version', 1)])

        purge.remove_unit_duplicate_nevra(unit_key, type_id, repo_id)

        # verify
        self.assertEqual(mock_criteria.mock_calls[0][2]['type_ids'], 'rpm')
        self.assertEqual(mock_criteria.mock_calls[0][2]['unit_filters'].keys(), ['$and'])
        result_filters = mock_criteria.mock_calls[0][2]['unit_filters']['$and']
        unit_filters = set()
        for i in result_filters:
            unit_filters.add(i.items()[0])
        self.assertEqual(unit_filters, expected_filters)
        mock_association.unassociate_by_criteria.assert_called_once_with(
            repo_id,
            mock_criteria.return_value)
