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
from xml.etree import cElementTree as cET

from pulp_rpm.plugins.importers.yum import utils
from pulp_rpm.plugins.importers.yum.repomd import primary


class TestElementToRawXML(unittest.TestCase):
    def setUp(self):
        foo = cET.fromstring(PRIMARY_XML)
        self.element = foo[0]

    def test_rpm(self):
        namespaces = [
            utils.Namespace('', primary.COMMON_SPEC_URL),
            utils.Namespace('rpm', primary.RPM_SPEC_URL),
        ]
        raw_xml = utils.element_to_raw_xml(self.element, namespaces)

        # make sure it stripped out any namespace declarations and root elements
        self.assertTrue(raw_xml.startswith('<package type="rpm">'))
        # make sure there are no stray closing elements, like </metadata>
        self.assertTrue(raw_xml.rstrip().endswith('</package>'))
        # make sure it preserved the "rpm" prefix
        self.assertTrue(raw_xml.find('<rpm:license>') >= 0)
        # make sure it got the requires and provides entries
        self.assertTrue(raw_xml.find('dolphin') >= 0)
        self.assertTrue(raw_xml.find('penguin') >= 0)


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


PRIMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="32">
<package type="rpm">
  <name>penguin</name>
  <arch>noarch</arch>
  <version epoch="0" ver="0.9.1" rel="1"/>
  <checksum type="sha256" pkgid="YES">57d314cc6f5322484cdcd33f4173374de95c53034de5b1168b9291ca0ad06dec</checksum>
  <summary>A dummy package of penguin</summary>
  <description>A dummy package of penguin</description>
  <packager></packager>
  <url>http://tstrachota.fedorapeople.org</url>
  <time file="1331832459" build="1331831373"/>
  <size package="2464" installed="42" archive="296"/>
<location href="penguin-0.9.1-1.noarch.rpm"/>
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor/>
    <rpm:group>Internet/Applications</rpm:group>
    <rpm:buildhost>smqe-ws15</rpm:buildhost>
    <rpm:sourcerpm>penguin-0.9.1-1.src.rpm</rpm:sourcerpm>
    <rpm:header-range start="872" end="2313"/>
    <rpm:provides>
      <rpm:entry name="penguin" flags="EQ" epoch="0" ver="0.9.1" rel="1"/>
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="dolphin"/>
    </rpm:requires>
  </format>
</package>
</metadata>
"""