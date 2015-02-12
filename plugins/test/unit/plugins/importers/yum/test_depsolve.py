# -*- coding: utf-8 -*-
"""
Test the pulp_rpm.plugins.importers.yum.depsolve module.
"""

import unittest

import mock
from pulp.plugins.model import Unit

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import depsolve


class DepsolveTestCase(unittest.TestCase):
    """
    The test case superclass for this module. It makes some RPMs that are useful for depsolve tests.
    """

    def _make_units(self, rpms):
        """
        Turn each of the rpms in the list into self.unit_# (where # is the index of the RPM plus
        one), and also save the generated units as self.units.
        """
        self.units = []
        for i, rpm in enumerate(rpms):
            unit = Unit(rpm.TYPE, rpm.unit_key, rpm.metadata, '')
            setattr(self, 'unit_%s' % i, unit)
            self.units.append(unit)

    def setUp(self):
        """
        Build some test RPMs with some dependencies.
        """
        self.rpm_0 = models.RPM(
            'firefox', '0', '23.0.0', '1', 'x86_64', 'sha256', 'some_sum',
            {'requires': [{'name': 'xulrunner', 'version': '23.0', 'release': '1',
                           'flags': depsolve.Requirement.GE}],
             'provides': [{'name': 'webbrowser'}]})
        self.rpm_1 = models.RPM(
            'firefox', '0', '23.0.2', '1', 'x86_64', 'sha256', 'some_sum',
            {'requires': [{'name': 'xulrunner', 'version': '23.0', 'release': '1',
                           'flags': depsolve.Requirement.GE}],
             'provides': [{'name': 'webbrowser'}]})
        self.rpm_2 = models.RPM(
            'xulrunner', '0', '23.0.1', '1', 'x86_64', 'sha256', 'some_sum',
            {'requires': [{'name': 'sqlite', 'version': '3.7.17',
                           'flags': depsolve.Requirement.GE}]})
        self.rpm_3 = models.RPM(
            'sqlite', '0', '3.7.17', '1', 'x86_64', 'sha256', 'some_sum',
            {'requires': []})
        # Nothing depends on this one, so it shouldn't be returned by anything
        self.rpm_4 = models.RPM(
            'gnome-calculator', '0', '3.8.2', '1', 'x86_64', 'sha256', 'some_sum',
            {'requires': [{'name': 'glib2'}],
             'provides': [{'name': 'calculator'}]})
        self.rpm_5 = models.RPM(
            'glib2', '0', '2.36.3', '3', 'x86_64', 'sha256', 'some_sum',
            {'requires': []})
        self.rpm_6 = models.RPM(
            'gcalctool', '0', '5.28.2', '3', 'x86_64', 'sha256', 'some_sum',
            {'requires': [],
             'provides': [{'name': 'calculator'}]})
        self.rpms = [getattr(self, 'rpm_%s' % i) for i in range(7)]

        self._make_units(self.rpms)

        self.mock_search = mock.MagicMock()
        self.solver = depsolve.Solver(self.mock_search)


class TestBuildProvidesTree(DepsolveTestCase):
    """
    Test the _build_provides_tree() function.
    """

    def test_empty_provides(self):
        """
        Make sure the function can handle RPMs without provides data.
        """
        for u in self.units:
            u.metadata['provides'] = []
        self.mock_search.return_value = self.units

        tree = self.solver._build_provides_tree()

        self.assertEqual(tree, {})

    def test_no_source_packages(self):
        """
        Test when source_packages is the empty list.
        """
        self.mock_search.return_value = []

        tree = self.solver._build_provides_tree()

        self.assertEqual(tree, {})

    def test_with_provides(self):
        self.mock_search.return_value = self.units

        tree = self.solver._build_provides_tree()

        expected_tree = {
            'webbrowser': {
                'firefox': self.unit_1,
            },
            'calculator': {
                'gnome-calculator': self.unit_4,
                'gcalctool': self.unit_6
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
        fake_unit.metadata = {'provides': [{'name': 'foo', 'another_field': 'bar'}]}

        trimmed = self.solver._trim_provides(fake_unit)

        self.assertEquals(trimmed.metadata, {'provides': ['foo']})


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
        self.mock_search.side_effect = self._get_units

    def _get_units(self, criteria, as_generator=False):
        """
        Fake the conduit get_units() call. If there are unit_filters, assume they have an $or clause
        and filter self.units for the units that have the same unit keys as the or clause.
        Otherwise, return self.units.
        """
        if criteria.unit_filters:
            units = (unit for unit in self.units if unit.unit_key in criteria.unit_filters['$or'])
        else:
            units = (unit for unit in self.units)

        if as_generator:
            return units
        else:
            return list(units)

    def test_one_unit_with_dependencies(self):
        """
        Call find_dependent_rpms with the Firefox unit. It should return a dependency on xulrunner.
        """
        units = [self.unit_1]

        dependent_rpms = self.solver.find_dependent_rpms(units)

        # Firefox only depends directly on xulrunner
        expected_rpms = set([self.unit_2])
        self.assertEqual(dependent_rpms, expected_rpms)

    def test_two_units_with_dependencies(self):
        """
        Call find_dependent_rpms() with firefox and gnome-calcualtor. It should return xulrunner and
        glib2.
        """
        units = [self.unit_1, self.unit_4]

        dependent_rpms = self.solver.find_dependent_rpms(units)

        # Firefox only depends directly on xulrunner, and gnome-calculator needs glib2
        expected_rpms = set([self.unit_2, self.unit_5])
        self.assertEqual(dependent_rpms, expected_rpms)

    def test_with_no_dependencies(self):
        """
        Call with glib2, which doesn't list any dependencies.
        """
        units = [self.unit_5]

        dependent_rpms = self.solver.find_dependent_rpms(units)

        # The glib2 unit doesn't list any dependencies
        expected_rpms = set([])
        self.assertEqual(dependent_rpms, expected_rpms)

    def test_with_no_units(self):
        """
        Call with no units, which shouldn't return any dependencies.
        """
        units = []

        dependent_rpms = self.solver.find_dependent_rpms(units)

        expected_rpms = set([])
        self.assertEqual(dependent_rpms, expected_rpms)


class TestMatch(DepsolveTestCase):
    """
    Test the match() function.
    """

    def test_provides_matches_requires(self):
        """
        Assert that match correctly handles provides that match requires.
        """
        r_1 = depsolve.Requirement('webbrowser')
        r_2 = depsolve.Requirement('calculator')
        reqs = [r_1, r_2]
        self.mock_search.return_value = self.units

        satisfactions = self.solver.match(reqs)

        # The newer version of firefox, gnome-calculator, and gcalctool should be the members of
        # this set
        expected_satisfactions = set([self.unit_1, self.unit_4, self.unit_6])
        self.assertEqual(satisfactions, expected_satisfactions)


class TestRequirement(unittest.TestCase):
    """
    Test the Requirement class.
    """

    def test___init___no_flags(self):
        """
        Test the __init__() method with no flags, which should choose EQ by default.
        """
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
        """
        Test the __init__() method with no flags, which should choose EQ by default.
        """
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
        """
        Test that the __cmp__ method correctly raises ValueError when the names are not equal.
        """
        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test_1', 0, '1.0.01', '23')
        r_2 = depsolve.Requirement('test_2', 0, '1.0.1', '23')

        # This should return a negative value
        self.assertRaises(ValueError, r_1.__cmp__, r_2)

    def test___cmp___mine_equal_other(self):
        """
        Test that the __cmp__ method correctly measures one Requirement being equal to the other.
        """
        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test', 0, '1.0.01', '23')
        r_2 = depsolve.Requirement('test', 0, '1.0.1', '23')

        # This should return a negative value
        self.assertEqual(r_1.__cmp__(r_2), 0)

    def test___cmp___mine_greater_other(self):
        """
        Test that the __cmp__ method correctly measures one Requirement being greater than the
        other.
        """
        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test', 1, '1.0.01', '23')
        r_2 = depsolve.Requirement('test', 0, '1.0.2', '23')

        # This should return a negative value
        self.assertTrue(r_1.__cmp__(r_2) > 0)

    def test___cmp___mine_less_other(self):
        """
        Test that the __cmp__ method correctly measures one Requirement being less than the other.
        """
        # Put a tricky z bit on this one that should reduce to 1.0.1, just to make sure that it is
        # correctly evaluated
        r_1 = depsolve.Requirement('test', 0, '1.0.01', '23')
        r_2 = depsolve.Requirement('test', 0, '1.0.2', '23')

        # This should return a negative value
        self.assertTrue(r_1.__cmp__(r_2) < 0)

    def test___cmp___missing_release(self):
        """
        Test that the __cmp__ method correctly handles a missing release.
        """
        r_1 = depsolve.Requirement('test', 1, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.2')

        # This should return a negative value
        self.assertTrue(r_1.__cmp__(r_2) > 0)

    def test___eq___false(self):
        """
        Test the __eq__ method with dissimilar Requirements.
        """
        r_1 = depsolve.Requirement('test', 1, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.2')
        r_3 = depsolve.Requirement('test_2', 0, '1.0.2')

        self.assertFalse(r_1 == r_2)
        # Make sure that the name being different makes the comparison not equal
        self.assertFalse(r_2 == r_3)

    def test___eq___true(self):
        """
        Test the __eq__ method with equal Requirements.
        """
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
        """
        Test the __eq__ method with one object missing a release.
        """
        r_1 = depsolve.Requirement('test', epoch='1', version='1', release='1')
        r_2 = depsolve.Requirement('test', epoch='1', version='1')

        self.assertTrue(r_1 == r_2)
        self.assertTrue(r_2 == r_1)

    def test___ne___false(self):
        """
        Test the __ne__ method with equal Requirements.
        """
        r_1 = depsolve.Requirement('test', 0, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.1')

        self.assertFalse(r_1 != r_2)

    def test___ne___true(self):
        """
        Test the __ne__ method with dissimilar Requirements.
        """
        r_1 = depsolve.Requirement('test', 1, '1.0.1')
        r_2 = depsolve.Requirement('test', 0, '1.0.2')
        r_3 = depsolve.Requirement('test_2', 0, '1.0.2')

        self.assertTrue(r_1 != r_2)
        self.assertTrue(r_2 != r_3)

    def test___repr__(self):
        """
        Test the __repr__() method.
        """
        r = depsolve.Requirement('test', 1, '1.0.1', '2', depsolve.Requirement.GE)

        repr = r.__repr__()

        self.assertEqual(repr, 'Require(name=test, epoch=1, version=1.0.1, release=2, flags=GE)')

    def test_is_versioned_false(self):
        """
        Test the is_versioned() method for the False case.
        """
        self.assertEqual(
            depsolve.Requirement('test', version='').is_versioned, False)
        self.assertEqual(
            depsolve.Requirement('test', version=None).is_versioned, False)

    def test_is_versioned_true(self):
        """
        Test the is_versioned() method for the True case.
        """
        self.assertEqual(depsolve.Requirement('test', version='1.0.1').is_versioned, True)

    def test_fills_requirement_ge_false(self):
        """
        Test fills_requirement() with GE that is False.
        """
        rpm = models.RPM('firefox', 0, '23.0.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GE)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_ge_true(self):
        """
        Test fills_requirement() with GE that is True.
        """
        rpm_1 = models.RPM('firefox', 0, '23.0.2', '1', 'x86_64', 'sha256', 'some_sum', {})
        rpm_2 = models.RPM('firefox', 0, '23.0.1', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GE)

        self.assertEqual(requirement.fills_requirement(rpm_1), True)
        self.assertEqual(requirement.fills_requirement(rpm_2), True)

    def test_fills_requirement_gt_false(self):
        """
        Test fills_requirement() with GT that is False.
        """
        rpm = models.RPM('firefox', 0, '23.0.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GT)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_gt_true(self):
        """
        Test fills_requirement() with GT that is True.
        """
        rpm = models.RPM('firefox', 0, '23.0.2', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.GT)

        self.assertEqual(requirement.fills_requirement(rpm), True)

    def test_fills_requirement_le_false(self):
        """
        Test fills_requirement() with LE that is False.
        """
        rpm = models.RPM('firefox', 0, '23.0.2', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LE)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_le_true(self):
        """
        Test fills_requirement() with LE that is True.
        """
        rpm_1 = models.RPM('firefox', 0, '23.0.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        rpm_2 = models.RPM('firefox', 0, '23.0.1', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LE)

        self.assertEqual(requirement.fills_requirement(rpm_1), True)
        self.assertEqual(requirement.fills_requirement(rpm_2), True)

    def test_fills_requirement_lt_false(self):
        """
        Test fills_requirement() with LT that is False.
        """
        rpm = models.RPM('firefox', 0, '23.0.2', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LT)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_lt_true(self):
        """
        Test fills_requirement() with LT that is True.
        """
        rpm = models.RPM('firefox', 0, '23.0.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1', depsolve.Requirement.LT)

        self.assertEqual(requirement.fills_requirement(rpm), True)

    def test_fills_requirement_name_match_versioned(self):
        """
        A package with the name that the unversioned Requirement specifies should meet the
        Requirement.
        """
        rpm = models.RPM('firefox', 0, '23.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox')

        self.assertEqual(requirement.fills_requirement(rpm), True)

    def test_fills_requirement_name_mismatch(self):
        """
        A package with a different name than the Requirement's name should not meet the Requirement.
        """
        rpm = models.RPM('firefox', 0, '23.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('openssh-server', 0, '23.0', '1')

        # Because 'firefox' is different than 'openssh-server', the rpm doesn't satisfy the
        # requirement even though the versions are equal
        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_eq_versioned_false(self):
        """
        Test fille_requirement() when the EQ flag is set and it is versioned for the case when the
        RPM does not meet the requirement.
        """
        rpm = models.RPM('firefox', 0, '23.0.2', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0.1', '1',
                                           flags=depsolve.Requirement.EQ)

        self.assertEqual(requirement.fills_requirement(rpm), False)

    def test_fills_requirement_eq_versioned_true(self):
        """
        Test fille_requirement() when the EQ flag is set and it is versioned for the case when the
        RPM does meet the requirement.
        """
        rpm = models.RPM('firefox', 0, '23.0', '1', 'x86_64', 'sha256', 'some_sum', {})
        requirement = depsolve.Requirement('firefox', 0, '23.0', '1', flags=depsolve.Requirement.EQ)

        self.assertEqual(requirement.fills_requirement(rpm), True)
