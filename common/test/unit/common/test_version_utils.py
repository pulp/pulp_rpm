# -*- coding: utf-8 -*-
import unittest

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
        # All numbers are converted to their numeric value. So '10' becomes 10, '000230' becomes
        # 230, and '00000' becomes 0.
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
        # Each label is separated into a list of maximal alphabetic or numeric sections,
        # with separators (non-alphanumeric characters) ignored. If there is any extra
        # non-alphanumeric character at the end, that. So, '2.0.1' becomes ('2', '0', '1'),
        # while ('2xFg33.+f.5') becomes ('2', 'xFg', '33', 'f', '5').
        #
        # Test: the int segments still need to be encoded as ints as well, hence the 1-1 in the
        # second segment.
        self.assertEqual(encode('2.1alpha'), '01-2.01-1.$alpha')

    def test_non_letter_removal(self):
        # Each label is separated into a list of maximal alphabetic or numeric sections,
        # with separators (non-alphanumeric characters) ignored. So, '2.0.1' becomes
        # ('2', '0', '1'), while ('2xFg33.+f.5') becomes ('2', 'xFg', '33', 'f', '5').
        #
        # Test: Notice that the + is removed, in addition to the splitting apart of numbers and
        # letters.
        self.assertEqual(encode('2xFg33.+f.5'), '01-2.$xFg.02-33.$f.01-5')


class UtilityTests(unittest.TestCase):
    def test_is_int(self):
        self.assertTrue(version_utils._is_int('1'))
        self.assertTrue(version_utils._is_int('10'))
        self.assertTrue(version_utils._is_int('-3'))
        self.assertFalse(version_utils._is_int('.3'))
        self.assertTrue(not version_utils._is_int('foo'))
