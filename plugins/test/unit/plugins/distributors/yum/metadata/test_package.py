# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import unittest
from xml.etree import ElementTree

import mock
from pulp.devel.unit.server.util import compare_element
from pulp.plugins.model import Unit

from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_ENVIRONMENT
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
                         'default': True,
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

    def _generate_environment_unit(self, name):
        unit_key = {'id': name}
        unit_metadata = {'id': name,
                         'display_order': 0,
                         'name': name,
                         'description': name + u' – description',
                         'grouplist': [],
                         'optionlist': []}
        storage_path = os.path.join(self.working_dir, name)
        return Unit(TYPE_ID_PKG_ENVIRONMENT, unit_key, unit_metadata, storage_path)

    def test_write_root_tag_open(self):
        self.context._write_root_tag_open()
        self.context.metadata_file_handle.write.assert_called_once_with(
            '<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" '
            '"comps.dtd">\n<comps>')

    def test_write_root_tag_close(self):
        self.context._write_root_tag_open()
        self.context.metadata_file_handle.write.reset_mock()
        self.context._write_root_tag_close()
        self.context.metadata_file_handle.write.assert_called_once_with(
            '</comps>\n')

    def test_add_package_group_unit_metadata_minimal(self):
        group_unit = self._generate_group_unit('foo')
        self.context.add_package_group_unit_metadata(group_unit)
        source_str = '<group><id>foo</id><default>true</default><uservisible>true</uservisible' \
                     '><display_order>0' \
                     '</display_order><name>foo</name><description>foodescription' \
                     '</description><packagelist /></group>'
        source_element = ElementTree.fromstring(source_str)
        xml_str = self.context.metadata_file_handle.write.call_args[0][0]
        target_element = ElementTree.fromstring(xml_str)
        compare_element(source_element, target_element)

    def test_add_package_group_unit_metadata_complex(self):
        group_unit = self._generate_group_unit('foo')
        group_unit.metadata['translated_name'] = {u'af': u'af_name', u'ze': u'ze_name'}
        group_unit.metadata['default'] = False
        group_unit.metadata['langonly'] = u'bar'
        group_unit.metadata['translated_description'] = {u'af': u'af_desc', u'ze': u'ze_desc'}
        group_unit.metadata['mandatory_package_names'] = [u'package2', u'package1', u'package3']
        group_unit.metadata['default_package_names'] = [u'package6', u'package5', u'package4']
        group_unit.metadata['optional_package_names'] = [u'package9', u'package8', u'package7']
        group_unit.metadata['conditional_package_names'] = [(u'package10', u'foo,bar,baz')]
        self.context.add_package_group_unit_metadata(group_unit)
        source_str = '<group><id>foo</id>' \
                     '<default>false</default>' \
                     '<uservisible>true</uservisible><display_order>0' \
                     '</display_order><langonly>bar</langonly>' \
                     '<name>foo</name>' \
                     '<name xml:lang="af">af_name</name>' \
                     '<name xml:lang="ze">ze_name</name>' \
                     '<description>foodescription</description>' \
                     '<description xml:lang="af">af_desc</description>' \
                     '<description xml:lang="ze">ze_desc</description>' \
                     '<packagelist><packagereq type="mandatory">package1</packagereq>' \
                     '<packagereq type="mandatory">package2</packagereq>' \
                     '<packagereq type="mandatory">package3</packagereq>' \
                     '<packagereq type="default">package4</packagereq>' \
                     '<packagereq type="default">package5</packagereq>' \
                     '<packagereq type="default">package6</packagereq>' \
                     '<packagereq type="optional">package7</packagereq>' \
                     '<packagereq type="optional">package8</packagereq>' \
                     '<packagereq type="optional">package9</packagereq>' \
                     '<packagereq requires="foo,bar,baz" type="conditional">package10' \
                     '</packagereq>' \
                     '</packagelist></group>'
        source_element = ElementTree.fromstring(source_str)
        xml_str = self.context.metadata_file_handle.write.call_args[0][0]
        target_element = ElementTree.fromstring(xml_str)
        compare_element(source_element, target_element)

    def test_add_package_category_unit_metadata_minimal(self):
        category_unit = self._generate_category_unit('category_name')
        self.context.add_package_category_unit_metadata(category_unit)
        source_str = '<category><id>category_name</id><display_order>0</display_order>' \
                     '<name>category_name</name>' \
                     '<description>category_name – description</description>' \
                     '<grouplist /></category>'
        source_element = ElementTree.fromstring(source_str)
        xml_str = self.context.metadata_file_handle.write.call_args[0][0]
        target_element = ElementTree.fromstring(xml_str)
        compare_element(source_element, target_element)

    def test_add_package_category_unit_metadata_complex(self):
        unit = self._generate_category_unit('category_name')
        unit.unit_key['id'] = None
        unit.metadata['translated_name'] = {u'af': u'af_name', u'ze': u'ze_name'}
        unit.metadata['translated_description'] = {u'af': u'af_desc', u'ze': u'ze_desc'}
        unit.metadata['packagegroupids'] = [u'package2', u'package1']
        self.context.add_package_category_unit_metadata(unit)
        source_str = '<category><id>category_name</id><display_order>0</display_order>' \
                     '<name>category_name</name>' \
                     '<name xml:lang="af">af_name</name>' \
                     '<name xml:lang="ze">ze_name</name>' \
                     '<description>category_name – description</description>' \
                     '<description xml:lang="af">af_desc</description>' \
                     '<description xml:lang="ze">ze_desc</description>' \
                     '<grouplist>' \
                     '<groupid>package1</groupid>' \
                     '<groupid>package2</groupid>' \
                     '</grouplist>' \
                     '</category>'
        source_element = ElementTree.fromstring(source_str)
        xml_str = self.context.metadata_file_handle.write.call_args[0][0]
        target_element = ElementTree.fromstring(xml_str)
        compare_element(source_element, target_element)

    def test_add_package_environment_unit_metadata_simple(self):
        unit = self._generate_environment_unit('environment_name')
        self.context.add_package_environment_unit_metadata(unit)

        source_str = '<environment><id>environment_name</id><display_order>0</display_order>' \
                     '<name>environment_name</name>' \
                     '<description>environment_name – description</description>' \
                     '<grouplist /><optionlist /></environment>'
        source_element = ElementTree.fromstring(source_str)
        xml_str = self.context.metadata_file_handle.write.call_args[0][0]
        target_element = ElementTree.fromstring(xml_str)
        compare_element(source_element, target_element)

    def test_add_package_environment_unit_metadata_complex(self):
        unit = self._generate_environment_unit('environment_name')
        unit.unit_key['id'] = None
        unit.metadata['translated_name'] = {u'af': u'af_name', u'ze': u'ze_name'}
        unit.metadata['translated_description'] = {u'af': u'af_desc', u'ze': u'ze_desc'}
        unit.metadata['group_ids'] = [u'package2', u'package1']
        unit.metadata['options'] = [{'group': 'package3', 'default': False},
                                    {'group': u'package4', 'default': True}]
        self.context.add_package_environment_unit_metadata(unit)
        source_str = '<environment><id>environment_name</id><display_order>0</display_order>' \
                     '<name>environment_name</name>' \
                     '<name xml:lang="af">af_name</name>' \
                     '<name xml:lang="ze">ze_name</name>' \
                     '<description>environment_name – description</description>' \
                     '<description xml:lang="af">af_desc</description>' \
                     '<description xml:lang="ze">ze_desc</description>' \
                     '<grouplist><groupid>package1</groupid><groupid>package2</groupid>' \
                     '</grouplist><optionlist>' \
                     '<groupid>package3</groupid>' \
                     '<groupid default="true">package4</groupid>' \
                     '</optionlist></environment>'

        source_element = ElementTree.fromstring(source_str)
        xml_str = self.context.metadata_file_handle.write.call_args[0][0]
        target_element = ElementTree.fromstring(xml_str)
        compare_element(source_element, target_element)
