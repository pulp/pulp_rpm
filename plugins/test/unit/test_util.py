# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import inspect
import unittest

from pulp_rpm.plugins.importers.yum import utils


class TestPaginate(unittest.TestCase):
    def test_list(self):
        iterable = list(range(10))
        ret = utils.paginate(iterable, 3)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [(0,1,2), (3,4,5), (6,7,8), (9,)])

    def test_list_one_page(self):
        iterable = list(range(10))
        ret = utils.paginate(iterable, 100)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [tuple(range(10))])

    def test_empty_list(self):
        ret = utils.paginate([], 3)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [])

    def test_tuple(self):
        iterable = tuple(range(10))
        ret = utils.paginate(iterable, 3)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [(0,1,2), (3,4,5), (6,7,8), (9,)])

    def test_tuple_one_page(self):
        iterable = tuple(range(10))
        ret = utils.paginate(iterable, 100)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [tuple(range(10))])

    def test_generator(self):
        iterable = (x for x in range(10))
        ret = utils.paginate(iterable, 3)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [(0,1,2), (3,4,5), (6,7,8), (9,)])

    def test_generator_one_page(self):
        iterable = (x for x in range(10))
        ret = utils.paginate(iterable, 100)

        self.assertTrue(inspect.isgenerator(ret))

        pieces = list(ret)

        self.assertEqual(pieces, [tuple(range(10))])
