# -*- coding: utf-8 -*-
"""
Test the pulp_rpm.plugins.importers.yum.depsolve module.
"""

import mock
from pulp.common.compat import unittest

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import depsolve


def _make_unit(model, *key_field_values, **extra_fields):
    fields_dict = dict(zip(model.unit_key_fields, key_field_values))
    fields_dict.update(extra_fields)
    unit = model(**fields_dict)
    # version sort indices are needed to ensure only the latest versions of units are
    # returned, but they're created in the pre-save signal.
    # trigger that signal on the fake units we're creating with a 'sender' of None to get them
    model.pre_save_signal(None, unit)
    return unit


class DepsolveTestCase(unittest.TestCase):
    """
    The test case superclass for this module. It makes some RPMs that are useful for depsolve tests.
    """
    def setUp(self):
        # Build some test RPMs with some dependencies on each other
        self.rpm_0 = _make_unit(
            models.RPM,
            'firefox', '0', '23.0.0', '1', 'x86_64', 'sha256', 'some_sum',
            requires=[{'name': 'xulrunner', 'version': '23.0', 'release': '1',
                       'flags': depsolve.Requirement.GE}],
            provides=[{'name': 'webbrowser'}])
        self.rpm_1 = _make_unit(
            models.RPM,
            'firefox', '0', '23.0.2', '1', 'x86_64', 'sha256', 'some_sum',
            requires=[{'name': 'xulrunner', 'version': '23.0', 'release': '1',
                       'flags': depsolve.Requirement.GE}],
            provides=[{'name': 'webbrowser'}])
        self.rpm_2 = _make_unit(
            models.RPM,
            'xulrunner', '0', '23.0.1', '1', 'x86_64', 'sha256', 'some_sum',
            requires=[{'name': 'sqlite', 'version': '3.7.17',
                       'flags': depsolve.Requirement.GE}])
        self.rpm_3 = _make_unit(
            models.RPM,
            'sqlite', '0', '3.7.17', '1', 'x86_64', 'sha256', 'some_sum',
            requires=[])
        # Nothing depends on this one, so it shouldn't be returned by anything
        self.rpm_4 = _make_unit(
            models.RPM,
            'gnome-calculator', '0', '3.8.2', '1', 'x86_64', 'sha256', 'some_sum',
            requires=[{'name': 'glib2'}],
            provides=[{'name': 'calculator'}])
        self.rpm_5 = _make_unit(
            models.RPM,
            'glib2', '0', '2.36.3', '3', 'x86_64', 'sha256', 'some_sum',
            requires=[])
        self.rpm_6 = _make_unit(
            models.RPM,
            'gcalctool', '0', '5.28.2', '3', 'x86_64', 'sha256', 'some_sum',
            requires=[],
            provides=[{'name': 'calculator'}])

        # list of all the rpms just created so they can be easily modified in bulk if needed
        self.rpms = [getattr(self, 'rpm_%s' % i) for i in range(7)]

        # fake repo for the solver to use, just needs a repo_id
        self.repo = mock.Mock()
        self.repo.repo_id = 'depsolving_repo'

        # the main thing being tested, the dependency Solver
        self.solver = depsolve.Solver(self.repo)

        # replace calls out to the repo controller by mocking out the unit generator, since
        # the repo controller will try to read from the db and never find matches there
        # to properly use this mock, you probably want to use self._rpm_generator,
        # since it has the same return signature as Solver._unit_generator
        search_patcher = mock.patch.object(depsolve.Solver, '_unit_generator')
        self.unit_generator = search_patcher.start()
        self.addCleanup(search_patcher.stop)

    def _rpm_generator(self, rpms=None):
        # depsolve's unit generator returns a generator of rpm content units.
        # this makes it easy for unit generator mock return values to also be a generator
        # note that you can pass an empty list to get back a generator that yields no values
        if rpms is None:
            rpms = self.rpms

        for rpm in rpms:
            yield rpm


class TestBuildProvidesTree(DepsolveTestCase):
    """
    Test the _build_provides_tree() function.
    """

    def test_empty_provides(self):
        # Make sure the function can handle RPMs without provides data.

        # clear all rpm provides, but search still returns all rpms
        for u in self.rpms:
            u.provides = []
        self.unit_generator.return_value = self._rpm_generator()
        tree = self.solver._build_provides_tree()

        # no rpms provide anything, dependency tree is empty
        self.assertEqual(tree, {})

    def test_no_source_packages(self):
        # Test when source_packages is the empty list.

        # rpms keep their provides data, but search returns no units
        self.unit_generator.return_value = []

        # build provides tree
        tree = self.solver._build_provides_tree()

        # no rpms found in search, dependency tree is empty
        self.assertEqual(tree, {})

    def test_with_provides(self):
        self.maxDiff = None
        self.unit_generator.return_value = self.rpms

        tree = self.solver._build_provides_tree()

        expected_tree = {
            'webbrowser': {
                'firefox': self.rpm_1,
            },
            'calculator': {
                'gnome-calculator': self.rpm_4,
                'gcalctool': self.rpm_6
            }
        }

        self.assertEqual(tree, expected_tree)


class TestProvidesTree(DepsolveTestCase):
    @mock.patch('pulp_rpm.plugins.importers.yum.depsolve.Solver._build_provides_tree')
    def test_returns_tree(self, mock_build):
        ret = self.solver._provides_tree

        mock_build.assert_called_once_with()
        self.assertEqual(ret, mock_build.return_value)

    @mock.patch('pulp_rpm.plugins.importers.yum.depsolve.Solver._build_provides_tree')
    def test_cache(self, mock_build):
        rets = [self.solver._provides_tree for x in range(5)]

        mock_build.assert_called_once_with()
        # make sure they are all the same
        self.assertTrue(reduce(lambda x, y: x if x is y else False, rets))

    def test_clear_source_cache(self):
        self.solver._packages_tree

        # the source list should be cached
        self.assertTrue(self.solver._cached_source_with_provides is not None)

        self.solver._provides_tree

        # the source list should have been cleared
        self.assertTrue(self.solver._cached_source_with_provides is None)

    def test_trim_provides(self):
        fake_unit = mock.Mock()
        fake_unit.provides = [{'name': 'foo', 'another_field': 'bar'}]

        trimmed = self.solver._trim_provides(fake_unit)

        self.assertEquals(trimmed.provides, ['foo'])


class TestPackagesTree(DepsolveTestCase):
    @mock.patch('pulp_rpm.plugins.importers.yum.depsolve.Solver._build_packages_tree')
    def test_returns_tree(self, mock_build):
        ret = self.solver._packages_tree

        mock_build.assert_called_once_with()
        self.assertEqual(ret, mock_build.return_value)

    @mock.patch('pulp_rpm.plugins.importers.yum.depsolve.Solver._build_packages_tree')
    def test_cache(self, mock_build):
        rets = [self.solver._packages_tree for x in range(5)]

        mock_build.assert_called_once_with()
        # make sure they are all the same
        self.assertTrue(reduce(lambda x, y: x if x is y else False, rets))

    def test_clear_source_cache(self):
        self.solver._provides_tree

        # the source list should be cached
        self.assertTrue(self.solver._cached_source_with_provides is not None)

        self.solver._packages_tree

        # the source list should have been cleared
        self.assertTrue(self.solver._cached_source_with_provides is None)


class TestFindDependentRPMs(DepsolveTestCase):
    """
    Test the find_dependent_rpms() function.
    """

    def setUp(self):
        super(TestFindDependentRPMs, self).setUp()
        self.unit_generator.return_value = self._rpm_generator()

    def test_one_unit_with_dependencies(self):
        # Call find_dependent_rpms with the Firefox unit.
        # It should return a dependency on xulrunner
        units = [self.rpm_1]

        # The DB query exists to add fields to the units. That isn't needed here, since the
        # pre-cooked units (self.rpm_1 for example) already have all the fields. So the mock
        # just returns the original units as-is.
        with mock.patch.object(models.RPM, 'objects') as mock_objects:
            mock_objects.filter.return_value.only.return_value = units

            dependent_rpms = self.solver.find_dependent_rpms(units)

        # Firefox only depends directly on xulrunner
        expected_rpms = set([self.rpm_2])
        self.assertEqual(dependent_rpms, expected_rpms)

    def test_two_units_with_dependencies(self):
        # Call find_dependent_rpms() with firefox and gnome-calculator.
        # It should return xulrunner and glib2.
        units = [self.rpm_1, self.rpm_4]

        # The DB query exists to add fields to the units. That isn't needed here, since the
        # pre-cooked units (self.rpm_1 for example) already have all the fields. So the mock
        # just returns the original units as-is.
        with mock.patch.object(models.RPM, 'objects') as mock_objects:
            mock_objects.filter.return_value.only.return_value = units

            dependent_rpms = self.solver.find_dependent_rpms(units)

        # Firefox only depends directly on xulrunner, and gnome-calculator needs glib2
        expected_rpms = set([self.rpm_2, self.rpm_5])
        self.assertEqual(dependent_rpms, expected_rpms)

    def test_with_no_dependencies(self):
        # Call with glib2, which doesn't list any dependencies.
        units = [self.rpm_5]

        dependent_rpms = self.solver.find_dependent_rpms(units)

        # The glib2 unit doesn't list any dependencies
        expected_rpms = set([])
        self.assertEqual(dependent_rpms, expected_rpms)

    def test_with_no_units(self):
        # Call with no units, which shouldn't return any dependencies.
        units = []

        dependent_rpms = self.solver.find_dependent_rpms(units)

        expected_rpms = set([])
        self.assertEqual(dependent_rpms, expected_rpms)


class TestMatch(DepsolveTestCase):
    """
    Test the match() function.
    """

    def test_provides_matches_requires(self):
        # Assert that match correctly handles provides that match requires.
        r_1 = depsolve.Requirement('webbrowser')
        r_2 = depsolve.Requirement('calculator')
        reqs = [r_1, r_2]
        self.unit_generator.return_value = self._rpm_generator()

        satisfactions = self.solver.match(reqs)

        # The newer version of firefox, gnome-calculator, and gcalctool should be the members of
        # this set
        expected_satisfactions = set([self.rpm_1, self.rpm_4, self.rpm_6])
        self.assertEqual(satisfactions, expected_satisfactions)


class TestRequirement(unittest.TestCase):
    """
    Test the Requirement class.
    """

    def test___init___no_flags(self):
        # Test the __init__() method with no flags, which should choose EQ by default.
        name = 'test'
        epoch = 0
        version = '1.0.1'
        release = '21'

        r = depsolve.Requirement(name, epoch, version, release)

        self.assertEqual(r.name, name)
        self.assertEqual(r.epoch, epoch)
        self.assertEqual(r.version, version)
        self.assertEqual(r.release, release)
        self.assertEqual(r.flags, depsolve.Requirement.EQ)

    def test___init___with_flags(self):
        # Test the __init__() method with no flags, which should choose EQ by default.
        name = 'test'
        epoch = 0
        version = '1.0.1'
        release = '21'
        flags = depsolve.Requirement.GE

        r = depsolve.Requirement(name, epoch, version, release, flags)

        self.assertEqual(r.name, name)
        self.assertEqual(r.epoch, epoch)
        self.assertEqual(r.version, version)
        self.assertEqual(r.release, release)
        self.assertEqual(r.flags, flags)

    def test___cmp___disparate_names(self):
        # Test that the __cmp__ method correctly raises ValueError when the names are not equal.

        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test_1', 0, '1.0.01', '23')
        r_2 = depsolve.Requirement('test_2', 0, '1.0.1', '23')

        # This should return a negative value
        self.assertRaises(ValueError, r_1.__cmp__, r_2)

    def test___cmp___mine_equal_other(self):
        # Test that the __cmp__ method correctly measures one Requirement being equal to the other.

        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test', 0, '1.0.01', '23')
        r_2 = depsolve.Requirement('test', 0, '1.0.1', '23')

        # This should return a negative value
        self.assertEqual(r_1.__cmp__(r_2), 0)

    def test___cmp___mine_greater_other(self):
        # Test that the __cmp__ method correctly measures one Requirement being greater than the
        # other.

        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test', 1, '1.0.01', '23')
        r_2 = depsolve.Requirement('test', 0, '1.0.2', '23')

        # This should return a negative value
        self.assertTrue(r_1.__cmp__(r_2) > 0)

    def test___cmp___mine_less_other(self):
        # Test that the __cmp__ method correctly measures one Requirement being less than the other

        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test', 0, '1.0.01', '23')
        r_2 = depsolve.Requirement('test', 0, '1.0.2', '23')

        # This should return a negative value
        self.assertTrue(r_1.__cmp__(r_2) < 0)

    def test___cmp___missing_release(self):
        # Test that the __cmp__ method correctly handles a missing release.

        r_1 = depsolve.Requirement('test', 1, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.2')

        # This should return a negative value
        self.assertTrue(r_1.__cmp__(r_2) > 0)

    def test___eq___false(self):
        # Test the __eq__ method with dissimilar Requirements.
        r_1 = depsolve.Requirement('test', 1, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.2')
        r_3 = depsolve.Requirement('test_2', 0, '1.0.2')

        self.assertFalse(r_1 == r_2)
        # Make sure that the name being different makes the comparison not equal
        self.assertFalse(r_2 == r_3)

    def test___eq___true(self):
        # Test the __eq__ method with equal Requirements.
        r_1 = depsolve.Requirement('test', 0, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.1')

        self.assertTrue(r_1 == r_2)

    def test__eq__leading_version_zeroes(self):
        r_1 = depsolve.Requirement('test', epoch='0', version='1', release='0')
        r_2 = depsolve.Requirement('test', epoch='0', version='01', release='0')

        self.assertTrue(r_1 == r_2)

    def test__eq__leading_release_zeroes(self):
        r_1 = depsolve.Requirement('test', epoch='0', version='0', release='1')
        r_2 = depsolve.Requirement('test', epoch='0', version='0', release='01')

        self.assertTrue(r_1 == r_2)

    def test__eq__no_release(self):
        # Test the __eq__ method with one object missing a release.
        r_1 = depsolve.Requirement('test', epoch='1', version='1', release='1')
        r_2 = depsolve.Requirement('test', epoch='1', version='1')

        self.assertTrue(r_1 == r_2)
        self.assertTrue(r_2 == r_1)

    def test___ne___false(self):
        # Test the __ne__ method with equal Requirements.
        r_1 = depsolve.Requirement('test', 0, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.1')

        self.assertFalse(r_1 != r_2)

    def test___ne___true(self):
        # Test the __ne__ method with dissimilar Requirements.
        r_1 = depsolve.Requirement('test', 1, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.2')
        r_3 = depsolve.Requirement('test_2', 0, '1.0.2')

        self.assertTrue(r_1 != r_2)
        self.assertTrue(r_2 != r_3)

    def test___repr__(self):
        # Test the __repr__() method.
        r = depsolve.Requirement('test', 1, '1.0.1', '2', depsolve.Requirement.GE)

        repr = r.__repr__()

        self.assertEqual(repr, 'Require(name=test, epoch=1, version=1.0.1, release=2, flags=GE)')

    def test_is_versioned_false(self):
        # Test the is_versioned() method for the False case.
        self.assertEqual(
            depsolve.Requirement('test', version='').is_versioned, False)
        self.assertEqual(
            depsolve.Requirement('test', version=None).is_versioned, False)

    def test_is_versioned_true(self):
        # Test the is_versioned() method for the True case.
        self.assertEqual(depsolve.Requirement('test', version='1.0.1').is_versioned, True)

    def test_fills_requirement_ge_false(self):
        # Test fills_requirement() with GE that is False.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.0', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GE)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_ge_true(self):
        # Test fills_requirement() with GE that is True.
        rpm_1 = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.2', release='1',
                           arch='x86_64', checksumtype='sha256', checksum='some_sum')
        rpm_2 = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.1', release='1',
                           arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GE)

        self.assertEqual(requirement.fills_requirement(rpm_1), True)
        self.assertEqual(requirement.fills_requirement(rpm_2), True)

    def test_fills_requirement_gt_false(self):
        # Test fills_requirement() with GT that is False.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.0', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GT)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_gt_true(self):
        # Test fills_requirement() with GT that is True.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.2', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GT)

        self.assertEqual(requirement.fills_requirement(rpm), True)

    def test_fills_requirement_le_false(self):
        # Test fills_requirement() with LE that is False.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.2', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LE)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_le_true(self):
        # Test fills_requirement() with LE that is True.
        rpm_1 = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.0', release='1',
                           arch='x86_64', checksumtype='sha256', checksum='some_sum')
        rpm_2 = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.1', release='1',
                           arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LE)

        self.assertEqual(requirement.fills_requirement(rpm_1), True)
        self.assertEqual(requirement.fills_requirement(rpm_2), True)

    def test_fills_requirement_lt_false(self):
        # Test fills_requirement() with LT that is False.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.2', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LT)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_lt_true(self):
        # Test fills_requirement() with LT that is True.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.0', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LT)

        self.assertEqual(requirement.fills_requirement(rpm), True)

    def test_fills_requirement_name_match_versioned(self):
        # A package with the name that the unversioned Requirement
        # specifies should meet the Requirement.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox')

        self.assertEqual(requirement.fills_requirement(rpm), True)

    def test_fills_requirement_name_mismatch(self):
        # A package with a different name than the Requirement's name
        # should not meet the Requirement.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('openssh-server', 0, '23.0', '1')

        # Because 'firefox' is different than 'openssh-server', the rpm doesn't satisfy the
        # requirement even though the versions are equal
        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_eq_versioned_false(self):
        # Test fille_requirement() when the EQ flag is set and it is versioned for the case
        # when the RPM does not meet the requirement.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0.2', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1',
                                           flags=depsolve.Requirement.EQ)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_eq_versioned_true(self):
        # Test fille_requirement() when the EQ flag is set and it is versioned for the case
        # when the RPM does meet the requirement.
        rpm = _make_unit(models.RPM, name='firefox', epoch=0, version='23.0', release='1',
                         arch='x86_64', checksumtype='sha256', checksum='some_sum')
        requirement = depsolve.Requirement('firefox', 0, '23.0', '1', flags=depsolve.Requirement.EQ)

        self.assertEqual(requirement.fills_requirement(rpm), True)
