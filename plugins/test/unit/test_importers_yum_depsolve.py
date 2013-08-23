# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
"""
Test the pulp_rpm.plugins.importers.yum.depsolve module.
"""

import unittest

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import depsolve


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
        r_1 = depsolve.Requirement('test', 0, '1.0.01')
        r_2 = depsolve.Requirement('test', 0, '1.0.1')

        self.assertTrue(r_1 == r_2)

    def test___ne___false(self):
        """
        Test the __ne__ method with equal Requirements.
        """
        r_1 = depsolve.Requirement('test', 0, '1.0.01')
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
