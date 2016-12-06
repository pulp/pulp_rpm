# -*- coding: utf-8 -*-
import mock

from cStringIO import StringIO

from pulp.common.compat import unittest
from pulp.plugins.util.saxwriter import XMLWriter
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.distributors.yum.metadata.package import PackageXMLFileContext


class TestPackageXMLFileContext(unittest.TestCase):
    """
    Test correct generation of comps.xml file
    """
    @mock.patch('pulp.plugins.util.metadata_writer.MetadataFileContext._open_metadata_file_handle')
    def setUp(self, mock_parent_open_file_handle):
        self.context = PackageXMLFileContext('/foo')
        self.context.metadata_file_handle = StringIO()
        self.context._open_metadata_file_handle()

    def _generate_group_unit(self, name):
        """
        Generate package group unit.

        display_order is omitted on purpose, to check its default value

        :param name: name of the unit
        :type  name: str
        """
        unit_data = {'package_group_id': name,
                     'repo_id': 'repo1',
                     'user_visible': True,
                     'default': True,
                     'name': name,
                     'description': name + u'description',
                     'mandatory_package_names': [],
                     'default_package_names': [],
                     'optional_package_names': [],
                     'conditional_package_names': {}}
        return models.PackageGroup(**unit_data)

    def _generate_category_unit(self, name):
        """
        Generate package category unit.

        :param name: name of the unit
        :type  name: str
        """
        unit_data = {'package_category_id': name,
                     'display_order': 0,
                     'name': name,
                     'description': name + u' – description',
                     'packagegroupids': []}
        return models.PackageCategory(**unit_data)

    def _generate_environment_unit(self, name):
        """
        Generate package environment unit.

        :param name: name of the unit
        :type  name: str
        """
        unit_data = {'package_environment_id': name,
                     'display_order': 0,
                     'name': name,
                     'description': name + u' – description',
                     'group_ids': [],
                     'options': []}
        return models.PackageEnvironment(**unit_data)

    def _generate_langpacks_unit(self):
        """
        Generate package langpacks unit.
        """
        unit_data = {'matches': []}
        return models.PackageLangpacks(**unit_data)

    @mock.patch('pulp.plugins.util.metadata_writer.MetadataFileContext._open_metadata_file_handle')
    def test__open_metadata_file_handle(self, mock_parent_open_file_handle):
        """
        Test that parent method for opening file is called and the XML generator is instantiated.
        """
        self.context._open_metadata_file_handle()
        mock_parent_open_file_handle.assert_called_once_with()
        self.assertTrue(isinstance(self.context.xml_generator, XMLWriter))

    def test__write_file_header(self):
        """
        Test that the correct header is written.
        """
        self.context._write_file_header()
        expected_xml = '<?xml version="1.0" encoding="utf-8"?>\n' \
            '<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">\n' \
            '<comps'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_group_unit_metadata_minimal(self):
        """
        Test the generation of minimal package group unit.
        """
        group_unit = self._generate_group_unit('foo')
        self.context.add_package_group_unit_metadata(group_unit)
        expected_xml = '<group>\n' \
                       '  <id>foo</id>\n' \
                       '  <default>true</default>\n' \
                       '  <uservisible>true</uservisible>\n' \
                       '  <display_order>1024</display_order>\n' \
                       '  <name>foo</name>\n' \
                       '  <description>foodescription</description>\n' \
                       '  <packagelist />\n' \
                       '</group>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_group_unit_metadata_complex(self):
        """
        Test the generation of complex package group unit.
        """
        group_unit = self._generate_group_unit('foo')
        group_unit.translated_name = {u'af': u'af_name', u'ze': u'ze_name'}
        group_unit.default = False
        group_unit.langonly = u'bar'
        group_unit.translated_description = {u'af': u'af_desc', u'ze': u'ze_desc'}
        group_unit.mandatory_package_names = [u'package2', u'package1', u'package3']
        group_unit.default_package_names = [u'package6', u'package5', u'package4']
        group_unit.optional_package_names = [u'package9', u'package8', u'package7']
        group_unit.conditional_package_names = [(u'package10', u'foo,bar,baz')]
        self.context.add_package_group_unit_metadata(group_unit)
        expected_xml = '<group>\n' \
                       '  <id>foo</id>\n' \
                       '  <default>false</default>\n' \
                       '  <uservisible>true</uservisible>\n' \
                       '  <display_order>1024</display_order>\n' \
                       '  <langonly>bar</langonly>\n' \
                       '  <name>foo</name>\n' \
                       '  <name xml:lang="af">af_name</name>\n' \
                       '  <name xml:lang="ze">ze_name</name>\n' \
                       '  <description>foodescription</description>\n' \
                       '  <description xml:lang="af">af_desc</description>\n' \
                       '  <description xml:lang="ze">ze_desc</description>\n' \
                       '  <packagelist>\n' \
                       '    <packagereq type="mandatory">package1</packagereq>\n' \
                       '    <packagereq type="mandatory">package2</packagereq>\n' \
                       '    <packagereq type="mandatory">package3</packagereq>\n' \
                       '    <packagereq type="default">package4</packagereq>\n' \
                       '    <packagereq type="default">package5</packagereq>\n' \
                       '    <packagereq type="default">package6</packagereq>\n' \
                       '    <packagereq type="optional">package7</packagereq>\n' \
                       '    <packagereq type="optional">package8</packagereq>\n' \
                       '    <packagereq type="optional">package9</packagereq>\n' \
                       '    <packagereq requires="foo,bar,baz" type="conditional">'\
                       'package10</packagereq>\n' \
                       '  </packagelist>\n' \
                       '</group>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_category_unit_metadata_minimal(self):
        """
        Test the generation of minimal package category unit.
        """
        category_unit = self._generate_category_unit('category_name')
        self.context.add_package_category_unit_metadata(category_unit)
        expected_xml = '<category>\n' \
                       '  <id>category_name</id>\n' \
                       '  <display_order>0</display_order>\n' \
                       '  <name>category_name</name>\n' \
                       '  <description>category_name – description</description>\n' \
                       '  <grouplist />\n' \
                       '</category>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_category_unit_metadata_complex(self):
        """
        Test the generation of complex package category unit.
        """
        unit = self._generate_category_unit('category_name')
        unit.translated_name = {u'af': u'af_name', u'ze': u'ze_name'}
        unit.translated_description = {u'af': u'af_desc', u'ze': u'ze_desc'}
        unit.packagegroupids = [u'package2', u'package1']
        self.context.add_package_category_unit_metadata(unit)
        expected_xml = '<category>\n' \
                       '  <id>category_name</id>\n' \
                       '  <display_order>0</display_order>\n' \
                       '  <name>category_name</name>\n' \
                       '  <name xml:lang="af">af_name</name>\n' \
                       '  <name xml:lang="ze">ze_name</name>\n' \
                       '  <description>category_name – description</description>\n' \
                       '  <description xml:lang="af">af_desc</description>\n' \
                       '  <description xml:lang="ze">ze_desc</description>\n' \
                       '  <grouplist>\n' \
                       '    <groupid>package1</groupid>\n' \
                       '    <groupid>package2</groupid>\n' \
                       '  </grouplist>\n' \
                       '</category>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_environment_unit_metadata_simple(self):
        """
        Test the generation of simple package environment unit.
        """
        unit = self._generate_environment_unit('environment_name')
        self.context.add_package_environment_unit_metadata(unit)
        expected_xml = '<environment>\n' \
                       '  <id>environment_name</id>\n' \
                       '  <display_order>0</display_order>\n' \
                       '  <name>environment_name</name>\n' \
                       '  <description>environment_name – description</description>\n' \
                       '  <grouplist />\n' \
                       '  <optionlist />\n' \
                       '</environment>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_environment_unit_metadata_complex(self):
        """
        Test the generation of complex package environment unit.
        """
        unit = self._generate_environment_unit('environment_name')
        unit.translated_name = {u'af': u'af_name', u'ze': u'ze_name'}
        unit.translated_description = {u'af': u'af_desc', u'ze': u'ze_desc'}
        unit.group_ids = [u'package2', u'package1']
        unit.options = [{'group': 'package3', 'default': False},
                        {'group': u'package4', 'default': True}]
        self.context.add_package_environment_unit_metadata(unit)
        expected_xml = '<environment>\n' \
                       '  <id>environment_name</id>\n' \
                       '  <display_order>0</display_order>\n' \
                       '  <name>environment_name</name>\n' \
                       '  <name xml:lang="af">af_name</name>\n' \
                       '  <name xml:lang="ze">ze_name</name>\n' \
                       '  <description>environment_name – description</description>\n' \
                       '  <description xml:lang="af">af_desc</description>\n' \
                       '  <description xml:lang="ze">ze_desc</description>\n' \
                       '  <grouplist>\n' \
                       '    <groupid>package1</groupid>\n' \
                       '    <groupid>package2</groupid>\n' \
                       '  </grouplist>\n' \
                       '  <optionlist>\n' \
                       '    <groupid>package3</groupid>\n' \
                       '    <groupid default="true">package4</groupid>\n' \
                       '  </optionlist>\n' \
                       '</environment>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_langpacks_unit_metadata_simple(self):
        """
        Test the generation of simple package langpacks unit.
        """
        unit = self._generate_langpacks_unit()
        self.context.add_package_langpacks_unit_metadata(unit)
        expected_xml = '<langpacks />\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)

    def test_add_package_langpacks_unit_metadata_complex(self):
        """
        Test the generation of complex package langpacks unit.
        """
        unit = self._generate_langpacks_unit()
        unit.matches = [{'install': 'package-%s', 'name': 'package-en'}]
        self.context.add_package_langpacks_unit_metadata(unit)
        expected_xml = '<langpacks>\n' \
                       '  <match name="package-en" install="package-%s" />\n' \
                       '</langpacks>\n'
        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml, expected_xml)
