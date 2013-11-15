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

import os
import shutil
import tempfile
import unittest

import mock
from pulp.plugins.model import Unit

from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY
from pulp_rpm.plugins.distributors.yum.metadata.package import PackageXMLFileContext


class TestPackageXMLFileContext(unittest.TestCase):

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.context = PackageXMLFileContext(self.working_dir)
        self.context.metadata_file_handle = mock.Mock()
        self.maxDiff = None
        self.context._write_root_tag_close = mock.Mock()

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def _generate_group_unit(self, name):
        unit_key = {'id': name}
        unit_metadata = {'user_visible': True,
                         'display_order': 0,
                         'name': name,
                         'description': name + u'description',
                         'mandatory_package_names': [],
                         'default_package_names': [],
                         'optional_package_names': [],
                         'conditional_package_names': {}}
        storage_path = os.path.join(self.working_dir, name)
        return Unit(TYPE_ID_PKG_GROUP, unit_key, unit_metadata, storage_path)

    def _generate_category_unit(self, name):
        unit_key = {'id': name}
        unit_metadata = {'id': name,
                         'user_visible': True,
                         'display_order': 0,
                         'name': name,
                         'description': name + u' – description',
                         'grouplist': []}
        storage_path = os.path.join(self.working_dir, name)
        return Unit(TYPE_ID_PKG_CATEGORY, unit_key, unit_metadata, storage_path)

    def test_write_root_tag_open(self):
        self.context._write_root_tag_open()
        self.context.metadata_file_handle.write.assert_called_once_with(
                          '<comps>\n<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" '
                          '"comps.dtd">\n')

    def test_add_package_group_unit_metadata_minimal(self):
        group_unit = self._generate_group_unit('foo')
        self.context.add_package_group_unit_metadata(group_unit)
        self.context.metadata_file_handle.write.assert_called_once_with(
                          '<group><id>foo</id><uservisible>true</uservisible><display_order>0'
                          '</display_order><name>foo</name><description>foodescription'
                          '</description><packagelist /></group>')

    def test_add_package_group_unit_metadata_complex(self):
        group_unit = self._generate_group_unit('foo')
        group_unit.metadata['translated_name'] = {u'af': u'af_name', u'ze': u'ze_name'}
        group_unit.metadata['langonly'] = u'bar'
        group_unit.metadata['translated_description'] = {u'af': u'af_desc', u'ze': u'ze_desc'}
        group_unit.metadata['mandatory_package_names'] = [u'package2', u'package1', u'package3']
        group_unit.metadata['default_package_names'] = [u'package6', u'package5', u'package4']
        group_unit.metadata['optional_package_names'] = [u'package9', u'package8', u'package7']
        group_unit.metadata['conditional_package_names'] = [(u'package10', u'foo,bar,baz')]
        self.context.add_package_group_unit_metadata(group_unit)
        self.context.metadata_file_handle.write.assert_called_once_with(
                          '<group><id>foo</id><uservisible>true</uservisible><display_order>0'
                          '</display_order><langonly>bar</langonly>'
                          '<name>foo</name><name xml:lang="ze">ze_name</name>'
                          '<name xml:lang="af">af_name</name><description>foodescription'
                          '</description><description xml:lang="ze">ze_desc</description>'
                          '<description xml:lang="af">af_desc</description>'
                          '<packagelist><packagereq type="mandatory">package1</packagereq>'
                          '<packagereq type="mandatory">package2</packagereq>'
                          '<packagereq type="mandatory">package3</packagereq>'
                          '<packagereq type="default">package4</packagereq>'
                          '<packagereq type="default">package5</packagereq>'
                          '<packagereq type="default">package6</packagereq>'
                          '<packagereq type="optional">package7</packagereq>'
                          '<packagereq type="optional">package8</packagereq>'
                          '<packagereq type="optional">package9</packagereq>'
                          '<packagereq requires="foo,bar,baz" type="conditional">package10</packagereq>'
                          '</packagelist></group>')

    def test_add_package_category_unit_metadata_minimal(self):
        category_unit = self._generate_category_unit('category_name')
        self.context.add_package_category_unit_metadata(category_unit)
        self.context.metadata_file_handle.write.assert_called_once_with(
                          '<category><id>category_name</id><display_order>0</display_order>'
                          '<name>category_name</name>'
                          '<description>category_name – description</description>'
                          '<grouplist /></category>')

    def test_add_package_category_unit_metadata_complex(self):

        unit = self._generate_category_unit('category_name')
        unit.unit_key['id'] = None
        unit.metadata['translated_name'] = {u'af': u'af_name', u'ze': u'ze_name'}
        unit.metadata['translated_description'] = {u'af': u'af_desc', u'ze': u'ze_desc'}
        unit.metadata['packagegroupids'] = [u'package2', u'package1']
        self.context.add_package_category_unit_metadata(unit)
        self.context.metadata_file_handle.write.assert_called_once_with(
                          '<category><id>category_name</id><display_order>0</display_order>'
                          '<name>category_name</name>'
                          '<name xml:lang="af">af_name</name>'
                          '<name xml:lang="ze">ze_name</name>'
                          '<description>category_name – description</description>'
                          '<description xml:lang="af">af_desc</description>'
                          '<description xml:lang="ze">ze_desc</description>'
                          '<grouplist>'
                          '<groupid>package1</groupid>'
                          '<groupid>package2</groupid>'
                          '</grouplist>'
                          '</category>')
