import unittest

import mock
from pulp.plugins.conduits.unit_import import ImportUnitConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Unit, Repository
from pulp.server.db.model.criteria import UnitAssociationCriteria
import pulp.server.managers.factory as manager_factory

import model_factory
from pulp_rpm.common import constants
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import associate


manager_factory.initialize()


@skip_broken
class TestAssociate(unittest.TestCase):
    def setUp(self):
        self.source_repo = Repository('repo-source')
        self.dest_repo = Repository('repo-dest')
        self.rpm_units = model_factory.rpm_units(2)
        self.category_units = model_factory.category_units(2)
        self.group_units = model_factory.group_units(2)
        self.group1_names = self.group_units[0].metadata['default_package_names']
        self.group2_names = self.group_units[1].metadata['default_package_names']
        self.conduit = mock.MagicMock()
        self.config = PluginCallConfiguration({}, {}, {})

    @mock.patch.object(associate, '_associate_unit', autospec=True)
    def test_no_units_provided(self, mock_associate):
        self.conduit.get_source_units.return_value = self.group_units

        associate.associate(self.source_repo, self.dest_repo, self.conduit, self.config)

        self.assertEqual(mock_associate.call_count, 2)
        # confirms that it used the conduit's get_source_units() method
        mock_associate.assert_any_call(self.dest_repo, self.conduit, self.group_units[0])
        mock_associate.assert_any_call(self.dest_repo, self.conduit, self.group_units[1])

    @mock.patch.object(associate, 'copy_rpms', autospec=True)
    def test_calls_copy_rpms(self, mock_copy_rpms):
        mock_copy_rpms.return_value = set(self.rpm_units)

        ret = associate.associate(self.source_repo, self.dest_repo, self.conduit,
                                  self.config, self.rpm_units)

        self.assertEqual(set(ret), set(self.rpm_units))

        self.assertEqual(mock_copy_rpms.call_count, 1)
        self.assertEqual(set(mock_copy_rpms.call_args[0][0]), set(self.rpm_units))
        self.assertEqual(mock_copy_rpms.call_args[0][1], self.conduit)
        self.assertFalse(mock_copy_rpms.call_args[0][2])

    @mock.patch.object(associate, 'copy_rpms_by_name', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units', autospec=True)
    @mock.patch.object(associate, '_associate_unit', wraps=lambda x, y, z: z)
    def test_copy_group_recursive(self, mock_associate, mock_get_existing, mock_copy):
        self.config.override_config = {constants.CONFIG_RECURSIVE: True}
        self.conduit.get_source_units.return_value = []
        # make it look like half of the RPMs named by the groups being copied
        # already exist in the destination
        existing_rpms = model_factory.rpm_units(2)
        existing_rpms[0].unit_key['name'] = self.group1_names[1]
        existing_rpms[1].unit_key['name'] = self.group2_names[1]
        existing_rpm_names = [self.group1_names[1], self.group2_names[1]]
        mock_get_existing.side_effect = iter([[], [], existing_rpms])
        mock_copy.return_value = set(u for u in self.rpm_units
                                     if u.unit_key['name'] not in existing_rpm_names)

        ret = associate.associate(self.source_repo, self.dest_repo, self.conduit,
                                  self.config, self.group_units)

        # this only happens if we successfully did a recursive call to associate()
        # and used the "existing" module to eliminate half the RPM names from those
        # that needed to be copied.
        mock_copy.assert_called_once_with(
            set([self.group1_names[0], self.group2_names[0]]),
            self.conduit, True)

        self.assertEqual(set(ret), set(self.group_units) | set(self.rpm_units))

    @mock.patch.object(associate, 'filter_available_rpms', autospec=True, return_value=[])
    @mock.patch.object(associate, 'copy_rpms', autospec=True)
    @mock.patch.object(associate, '_associate_unit', wraps=lambda x, y, z: z)
    def test_copy_categories(self, mock_associate_unit, mock_copy_rpms, mock_filter):
        mock_copy_rpms.return_value = set()
        self.config.override_config = {constants.CONFIG_RECURSIVE: True}
        groups_to_copy = model_factory.group_units(2)
        for group in groups_to_copy:
            group.metadata['default_package_names'] = []
        self.conduit.get_source_units.side_effect = [groups_to_copy, []]

        ret = associate.associate(self.source_repo, self.dest_repo, self.conduit,
                                  self.config, self.category_units)

        self.assertEqual(set(ret), set(self.category_units) | set(groups_to_copy))
        self.assertEqual(mock_associate_unit.call_count, 4)
        mock_associate_unit.assert_any_call(self.dest_repo, self.conduit, self.category_units[0])
        mock_associate_unit.assert_any_call(self.dest_repo, self.conduit, self.category_units[1])
        mock_associate_unit.assert_any_call(self.dest_repo, self.conduit, groups_to_copy[0])
        mock_associate_unit.assert_any_call(self.dest_repo, self.conduit, groups_to_copy[1])


@skip_broken
class TestCopyRPMs(unittest.TestCase):
    def test_without_deps(self):
        conduit = mock.MagicMock()
        rpms = model_factory.rpm_units(3)

        associate.copy_rpms(rpms, conduit, False)

        self.assertEqual(conduit.associate_unit.call_count, 3)
        for rpm in rpms:
            conduit.associate_unit.assert_any_call(rpm)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.depsolve.Solver.find_dependent_rpms', autospec=True)
    def test_with_existing_deps(self, mock_find, mock_get_existing):
        conduit = mock.MagicMock()
        rpms = model_factory.rpm_units(1)
        deps = model_factory.rpm_units(2)
        mock_find.return_value = set(deps)
        mock_get_existing.return_value = deps

        associate.copy_rpms(rpms, conduit, True)

        self.assertEqual(conduit.associate_unit.call_count, 1)
        self.assertEqual(mock_find.call_count, 1)
        self.assertEqual(mock_find.call_args[0][1], set(rpms))
        self.assertEqual(mock_get_existing.call_count, 1)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.depsolve.Solver.find_dependent_rpms', autospec=True)
    def test_with_recursive_deps(self, mock_find, mock_get_existing):
        """
        Test getting dependencies that do not exist in the repository already
        """
        conduit = mock.MagicMock()
        # Create the primary RPMS that we want to copy
        rpms = model_factory.rpm_units(1)

        # Create the recursive dependencies that we want to copy
        deps = model_factory.rpm_units(2)
        mock_find.side_effect = iter([set(deps), set()])

        # The get existing units always assumes there are no units in the target repository
        mock_get_existing.return_value = []
        unit_set = associate.copy_rpms(rpms, conduit, True)

        merged_set = set(deps)
        merged_set.update(rpms)
        self.assertEquals(unit_set, merged_set)


@skip_broken
class TestNoChecksumCleanUnitKey(unittest.TestCase):
    def test_all(self):
        rpm = model_factory.rpm_models(1)[0]

        ret = associate._no_checksum_clean_unit_key(rpm.as_named_tuple)

        self.assertTrue(isinstance(ret, dict))
        self.assertTrue('checksum' not in ret)
        self.assertTrue('checksumtype' not in ret)
        for key in ['name', 'epoch', 'version', 'release', 'arch']:
            self.assertEqual(ret[key], rpm.unit_key[key])

    def test_no_epoch(self):
        rpm = model_factory.rpm_models(1)[0]
        # simulates repos that don't have epochs in their errata
        rpm.epoch = None

        ret = associate._no_checksum_clean_unit_key(rpm.as_named_tuple)

        self.assertTrue(isinstance(ret, dict))
        self.assertTrue('epoch' not in ret)


@skip_broken
class TestCopyRPMsByName(unittest.TestCase):
    @mock.patch.object(associate, 'copy_rpms', autospec=True)
    def test_all_in_source(self, mock_copy):
        rpms = model_factory.rpm_units(2)
        names = [r.unit_key['name'] for r in rpms]
        conduit = mock.MagicMock()
        conduit.get_source_units.return_value = rpms

        associate.copy_rpms_by_name(names, conduit, False)

        self.assertEqual(conduit.get_source_units.call_count, 1)
        to_copy = list(mock_copy.call_args[0][0])
        self.assertEqual(len(to_copy), 2)
        for unit in to_copy:
            self.assertTrue(isinstance(unit, Unit))
            self.assertTrue(unit.unit_key['name'] in names)
        self.assertFalse(mock_copy.call_args[0][2])

    @mock.patch.object(associate, 'copy_rpms', autospec=True)
    def test_multiple_versions(self, mock_copy):
        rpms = model_factory.rpm_units(2, True)
        names = list(set([r.unit_key['name'] for r in rpms]))
        conduit = mock.MagicMock()
        conduit.get_source_units.return_value = rpms

        associate.copy_rpms_by_name(names, conduit, False)

        self.assertEqual(conduit.get_source_units.call_count, 1)
        to_copy = list(mock_copy.call_args[0][0])
        self.assertEqual(len(to_copy), 1)
        unit = to_copy[0]
        self.assertTrue(isinstance(unit, Unit))
        self.assertTrue(unit.unit_key['name'] in names)
        self.assertEqual(unit.unit_key['version'], rpms[1].unit_key['version'])
        self.assertFalse(mock_copy.call_args[0][2])


@skip_broken
class TestIdentifyChildrenToCopy(unittest.TestCase):
    def test_group(self):
        units = model_factory.group_units(1)

        groups, rpm_names, rpm_search_dicts = associate.identify_children_to_copy(units)

        self.assertEqual(len(groups), 0)
        self.assertEqual(len(rpm_search_dicts), 0)
        self.assertEqual(rpm_names, set(units[0].metadata['default_package_names']))

    def test_category(self):
        units = model_factory.category_units(1)

        groups, rpm_names, rpm_search_dicts = associate.identify_children_to_copy(units)

        self.assertEqual(len(rpm_names), 0)
        self.assertEqual(len(rpm_search_dicts), 0)
        self.assertEqual(groups, set(units[0].metadata['packagegroupids']))

    def test_environment(self):
        units = model_factory.environment_units(1)

        groups, rpm_names, rpm_search_dicts = associate.identify_children_to_copy(units)

        target_groups = set(units[0].metadata['group_ids'])
        target_groups.update([d.get('group') for d in units[0].metadata['options']])

        self.assertEqual(len(rpm_names), 0)
        self.assertEqual(len(rpm_search_dicts), 0)
        self.assertEqual(groups, target_groups)

    def test_erratum(self):
        units = model_factory.errata_units(1)

        groups, rpm_names, rpm_search_dicts = associate.identify_children_to_copy(units)

        self.assertEqual(len(rpm_names), 0)
        self.assertEqual(len(groups), 0)
        self.assertEqual(rpm_search_dicts, units[0].metadata['pkglist'][0]['packages'])


@skip_broken
class TestAssociateUnit(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')

    @mock.patch('shutil.copyfile')
    def test_rpm(self, mock_copyfile):
        model = model_factory.rpm_models(1)[0]
        unit = Unit(model.TYPE, model.unit_key, model.metadata, '/')

        # passing "None" ensures that the importer isn't being called
        ret = associate._associate_unit('', None, unit)

        self.assertTrue(ret is unit)
        self.assertEqual(mock_copyfile.call_count, 0)

    def test_distribution(self):
        unit = model_factory.drpm_units(1)[0]
        mock_conduit = mock.MagicMock(spec_set=ImportUnitConduit)

        ret = associate._associate_unit('repo2', mock_conduit, unit)

        self.assertTrue(ret is unit)
        mock_conduit.associate_unit.assert_called_once_with(unit)

    @mock.patch('shutil.copyfile')
    def test_yum_md_file(self, mock_copyfile):
        mock_conduit = mock.MagicMock(spec_set=ImportUnitConduit('', '', '', ''))
        model = model_factory.yum_md_file()
        unit = Unit(model.TYPE, model.unit_key, model.metadata, '/foo/bar')

        associate._associate_unit(self.repo, mock_conduit, unit)

        expected_key = {'repo_id': self.repo.id, 'data_type': model.unit_key['data_type']}
        self.assertEqual(mock_conduit.init_unit.call_args[0][0], model.TYPE)
        self.assertEqual(mock_conduit.init_unit.call_args[0][1], expected_key)
        self.assertEqual(mock_conduit.init_unit.call_args[0][2], model.metadata)

        mock_conduit.save_unit.assert_called_once_with(mock_conduit.init_unit.return_value)

        mock_copyfile.assert_called_once_with(unit.storage_path,
                                              mock_conduit.init_unit.return_value.storage_path)

    def test_group(self):
        unit = model_factory.group_units(1)[0]
        mock_conduit = mock.MagicMock()

        ret = associate._associate_unit(self.repo, mock_conduit, unit)

        saved_unit = mock_conduit.save_unit.call_args[0][0]

        self.assertTrue(ret is mock_conduit.save_unit.return_value)
        self.assertEqual(saved_unit.unit_key['repo_id'], self.repo.id)
        self.assertEqual(saved_unit.unit_key['id'], unit.unit_key['id'])


@skip_broken
class TestGetRPMSToCopyByKey(unittest.TestCase):
    def setUp(self):
        self.units = model_factory.rpm_units(2)
        self.search_dicts = [unit.unit_key for unit in self.units]
        self.conduit = mock.MagicMock()

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units',
                autospec=True, return_value=tuple())
    def test_none_existing(self, mock_get_existing):
        ret = associate.get_rpms_to_copy_by_key(self.search_dicts, self.conduit)

        self.assertTrue(isinstance(ret, set))
        self.assertEqual(len(ret), 2)
        expected1 = self.search_dicts[0]
        expected1['checksum'] = None
        expected1['checksumtype'] = None
        expected2 = self.search_dicts[0]
        expected2['checksum'] = None
        expected2['checksumtype'] = None
        self.assertTrue(models.RPM.NAMEDTUPLE(**expected1) in ret)
        self.assertTrue(models.RPM.NAMEDTUPLE(**expected2) in ret)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units',
                autospec=True)
    def test_some_existing(self, mock_get_existing):
        mock_get_existing.return_value = [self.units[0]]

        ret = associate.get_rpms_to_copy_by_key(self.search_dicts, self.conduit)

        self.assertTrue(isinstance(ret, set))
        self.assertEqual(len(ret), 1)
        expected = self.search_dicts[1]
        expected['checksum'] = None
        expected['checksumtype'] = None
        self.assertTrue(models.RPM.NAMEDTUPLE(**expected) in ret)

        mock_get_existing.assert_called_once_with(self.search_dicts, models.RPM.UNIT_KEY_NAMES,
                                                  models.RPM.TYPE,
                                                  self.conduit.get_destination_units)


@skip_broken
class TestGetRPMSToCopyByName(unittest.TestCase):
    RPM_NAMES = ('postfix', 'vim-common', 'python-mock')

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units',
                autospec=True, return_value=tuple())
    def test_none_existing(self, mock_get_existing):
        mock_conduit = mock.MagicMock(spec_set=ImportUnitConduit('', '', '', ''))

        ret = associate.get_rpms_to_copy_by_name(self.RPM_NAMES, mock_conduit)

        self.assertTrue(isinstance(ret, set))
        self.assertEqual(ret, set(self.RPM_NAMES))
        self.assertEqual(mock_get_existing.call_count, 1)
        self.assertEqual(list(mock_get_existing.call_args[0][0]),
                         list({'name': name} for name in self.RPM_NAMES))
        self.assertEqual(mock_get_existing.call_args[0][1], models.RPM.UNIT_KEY_NAMES)
        self.assertEqual(mock_get_existing.call_args[0][2], models.RPM.TYPE)
        self.assertEqual(mock_get_existing.call_args[0][3], mock_conduit.get_destination_units)

    def test_some_existing(self):
        postfix = model_factory.rpm_models(1)[0]
        postfix.name = 'postfix'
        vim = model_factory.rpm_models(1)[0]
        vim.name = 'vim-common'
        existing = [
            Unit(postfix.TYPE, postfix.unit_key, postfix.metadata, ''),
            Unit(vim.TYPE, vim.unit_key, vim.metadata, ''),
        ]
        conduit = ImportUnitConduit('', '', '', '')
        conduit.get_destination_units = mock.MagicMock(spec_set=conduit.get_destination_units,
                                                       return_value=existing)

        ret = associate.get_rpms_to_copy_by_name(self.RPM_NAMES, conduit)

        self.assertEqual(set(ret), set(['python-mock']))
        self.assertEqual(conduit.get_destination_units.call_count, 1)
        self.assertTrue(
            isinstance(conduit.get_destination_units.call_args[0][0], UnitAssociationCriteria))
        self.assertEqual(conduit.get_destination_units.call_args[0][0].type_ids, [models.RPM.TYPE])
        self.assertEqual(conduit.get_destination_units.call_args[0][0].unit_fields,
                         models.RPM.UNIT_KEY_NAMES)


@skip_broken
class TestSafeCopyWithoutFile(unittest.TestCase):
    def test_metadata_clear_keys_prefixed_with_underscore(self):
        unit = model_factory.group_units(1)[0]
        unit.metadata['_foo'] = 'value'
        copied_unit = associate._safe_copy_unit_without_file(unit)
        self.assertEquals(None, copied_unit.metadata.get('_foo'))
