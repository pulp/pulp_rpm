# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import unittest

import pymongo
from pulp.server.db import connection

import rpm_support_base
from pulp_rpm.common import version_utils
from pulp_rpm.common.version_utils import encode


class EncodeTests(unittest.TestCase):

    def test_empty_string(self):
        self.assertRaises(ValueError, encode, '')

    def test_none(self):
        self.assertRaises(TypeError, encode, None)

    def test_numbers(self):
        self.assertEqual(encode('1.1'), '01-1.01-1')
        self.assertEqual(encode('2.3'), '01-2.01-3')
        self.assertEqual(encode('3.10'), '01-3.02-10')
        self.assertEqual(encode('127.0.0.1'), '03-127.01-0.01-0.01-1')

    def test_leading_zeroes(self):
        # All numbers are converted to their numeric value. So '10' becomes 10, '000230' becomes 230,
        # and '00000' becomes 0.
        self.assertEqual(encode('1.001'), '01-1.01-1')

    def test_large_ints(self):
        self.assertEqual(encode('1.1234567890'), '01-1.10-1234567890')

    def test_really_large_ints(self):
        self.assertRaises(ValueError, encode, '1' * 100)

    def test_letters(self):
        self.assertEqual(encode('alpha'), '$alpha')
        self.assertEqual(encode('beta.gamma'), '$beta.$gamma')

    def test_both(self):
        self.assertEqual(encode('1.alpha'), '01-1.$alpha')
        self.assertEqual(encode('0.2.beta.1'), '01-0.01-2.$beta.01-1')

    def test_mixed(self):
        # Each label is separated into a list of maximal alphabetic or numeric sections, with separators
        # (non-alphanumeric characters) ignored. If there is any extra non-alphanumeric character at the
        # end, that. So, '2.0.1' becomes ('2', '0', '1'), while ('2xFg33.+f.5') becomes
        # ('2', 'xFg', '33', 'f', '5').
        #
        # Test: the int segments still need to be encoded as ints as well, hence the 1-1 in the second
        # segment.
        self.assertEqual(encode('2.1alpha'), '01-2.01-1.$alpha')

    def test_non_letter_removal(self):
        # Each label is separated into a list of maximal alphabetic or numeric sections, with separators
        # (non-alphanumeric characters) ignored. If there is any extra non-alphanumeric character at the
        # end, that. So, '2.0.1' becomes ('2', '0', '1'), while ('2xFg33.+f.5') becomes
        # ('2', 'xFg', '33', 'f', '5').
        #
        # Test: Notice that the + is removed, in addition to the splitting apart of numbers and letters.
        self.assertEqual(encode('2xFg33.+f.5'), '01-2.$xFg.02-33.$f.01-5')


class DatabaseSortTests(rpm_support_base.PulpRPMTests):
    """
    Tests using the database's sort capabilities rather than Python's to be closer to the
    actual usage.
    """

    def setUp(self):
        super(DatabaseSortTests, self).setUp()
        self.db = connection._database.test_version_compare

    def tearDown(self):
        connection._database.drop_collection('test_version_compare')

    def test_numbers(self):
        # If both the elements are numbers, the larger number is considered newer. So 5 is newer than 4
        # and 10 is newer than 2.
        self.assert_greater_than_or_equal('5', '4')
        self.assert_greater_than_or_equal('1.2', '1.1')
        self.assert_greater_than_or_equal('3.9', '3.1')
        self.assert_greater_than_or_equal('3.10', '3.9')
        self.assert_greater_than_or_equal('3.11', '3.10')

    def test_letters(self):
        self.assert_greater_than_or_equal('beta', 'alpha')
        self.assert_greater_than_or_equal('0.2.beta.1', '0.2.alpha.17')

    def test_letter_case(self):
        # If both the elements are alphabetic, they are compared using the Unix strcmp function, with the
        # greater string resulting in a newer element. So 'add' is newer than 'ZULU' (because lowercase
        # characters win in strcmp comparisons).
        self.assert_greater_than_or_equal('add', 'ZULU')  # see fedora link in version_utils

    def test_letters_v_numbers(self):
        # If one of the elements is a number, while the other is alphabetic, the numeric elements is
        # considered newer. So 10 is newer than 'abc', and 0 is newer than 'Z'.
        self.assert_greater_than_or_equal('0', 'Z')
        self.assert_greater_than_or_equal('10', 'abc')

    def test_mixed(self):
        # '2a' is older than '2.0', because numbers are considered newer than letters.
        self.assert_greater_than_or_equal('2.0', '2a')

    def test_different_length_ints(self):
        # The elements in the list are compared one by one using the following algorithm. In case one
        # of the lists run out, the other label wins as the newer label. So, for example, (1, 2) is
        # newer than (1, 1), and (1, 2, 0) is newer than (1, 2).
        self.assert_greater_than_or_equal('1.2', '1.1.0')
        self.assert_greater_than_or_equal('1.2.0', '1.2')

    def test_different_length_letters(self):
        # If both the elements are alphabetic, they are compared using the Unix strcmp function, with the
        # greater string resulting in a newer element. So 'aba' is newer than 'ab'.
        self.assert_greater_than_or_equal('aba', 'ab')

    def test_leading_zeroes(self):
        self.assert_greater_than_or_equal('1.002', '1.1')

    def assert_greater_than_or_equal(self, version1, version2):
        encoded1 = encode(version1)
        encoded2 = encode(version2)

        self.db.insert({'version' : version1, 'version_sort_index' : encoded1}, safe=True)
        self.db.insert({'version' : version2, 'version_sort_index' : encoded2}, safe=True)

        sorted_versions = self.db.find({}).sort([('version_sort_index', pymongo.DESCENDING)])

        msg = '[%s, %s] was less than [%s, %s]' % (version1, encoded1, version2, encoded2)
        self.assertEqual(sorted_versions[0]['version'], version1, msg=msg)

        self.db.remove()  # clean up for multiple calls to this in a single test


class UtilityTests(unittest.TestCase):

    def test_is_int(self):
        self.assertTrue(version_utils._is_int('1'))
        self.assertTrue(version_utils._is_int('10'))
        self.assertTrue(not version_utils._is_int('foo'))
