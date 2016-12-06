"""
This module is used for generating all metadata related to package groups and categories
"""
import os

from pulp.plugins.util.metadata_writer import XmlFileContext
from pulp.plugins.util.saxwriter import XMLWriter
from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

PACKAGE_XML_FILE_NAME = 'comps.xml'


class PackageXMLFileContext(XmlFileContext):
    """
    The PackageXMLFileContext is used to generate the comps.xml file used in yum repositories
    for storing information about package categories and package groups
    """

    def __init__(self, working_dir, checksum_type=None):
        """
        Initialize and set the file where the metadata is being saved.

        :param working_dir: root working directory where the repo is being generated.
        :type  working_dir: str
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, PACKAGE_XML_FILE_NAME)
        super(PackageXMLFileContext, self).__init__(metadata_file_path, 'comps',
                                                    checksum_type=checksum_type)

    def _open_metadata_file_handle(self):
        """
        Open the metadata file handle, creating any missing parent directories.
        If the file already exists, this will overwrite it.
        """
        super(PackageXMLFileContext, self)._open_metadata_file_handle()
        self.xml_generator = XMLWriter(self.metadata_file_handle, short_empty_elements=True)

    def _write_file_header(self):
        """
        Write out the beginning of the comps.xml file
        """
        self.xml_generator.startDocument()
        doctype = '<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">'
        self.xml_generator.writeDoctype(doctype)
        self.xml_generator.startElement(self.root_tag, self.root_attributes)

    def _write_translated_fields(self, tag_name, translated_fields):
        """
        Write out the xml for a translated field

        :param tag_name: The xml tag name to generate for the translated field
        :type tag_name: str
        :param translated_fields: The dictionary of locales and the translated text
        :type translated_fields: dict of locale to translated text
        """
        if translated_fields:
            for locale, field_text in sorted(translated_fields.iteritems()):
                self.xml_generator.completeElement(tag_name, {'xml:lang': locale}, field_text)

    def add_package_group_unit_metadata(self, group_unit):
        """
        Write out the XML representation of a group

        :param group_unit: the group to publish
        :type group_unit: pulp_rpm.plugins.db.models.PackageGroup
        """
        self.xml_generator.startElement('group', {})
        self.xml_generator.completeElement('id', {}, group_unit.package_group_id)
        self.xml_generator.completeElement('default', {}, str(group_unit.default).lower())
        self.xml_generator.completeElement('uservisible', {}, str(group_unit.user_visible).lower())

        # If the order is not specified, then 1024 should be set as default.
        # With value of 1024 the group will be displayed at the very bottom of the list.
        display_order = group_unit.display_order if group_unit.display_order is not None else 1024
        self.xml_generator.completeElement('display_order', {}, str(display_order))

        if group_unit.langonly:
            self.xml_generator.completeElement('langonly', {}, group_unit.langonly)
        self.xml_generator.completeElement('name', {}, group_unit.name)
        self._write_translated_fields('name', group_unit.translated_name)
        self.xml_generator.completeElement('description', {}, group_unit.description)
        self._write_translated_fields('description', group_unit.translated_description)

        self.xml_generator.startElement('packagelist', {})
        if group_unit.mandatory_package_names:
            for pkg in sorted(group_unit.mandatory_package_names):
                self.xml_generator.completeElement('packagereq', {'type': 'mandatory'}, pkg)
        if group_unit.default_package_names:
            for pkg in sorted(group_unit.default_package_names):
                self.xml_generator.completeElement('packagereq', {'type': 'default'}, pkg)
        if group_unit.optional_package_names:
            for pkg in sorted(group_unit.optional_package_names):
                self.xml_generator.completeElement('packagereq', {'type': 'optional'}, pkg)
        if group_unit.conditional_package_names:
            for pkg_name, value in group_unit.conditional_package_names:
                attrs = {'type': 'conditional', 'requires': value}
                self.xml_generator.completeElement('packagereq', attrs, pkg_name)
        self.xml_generator.endElement('packagelist')
        self.xml_generator.endElement('group')

    def add_package_category_unit_metadata(self, unit):
        """
        Write out the XML representation of a category unit

        :param unit: The category to publish
        :type unit: pulp_rpm.plugins.db.models.PackageCategory
        """
        self.xml_generator.startElement('category')
        self.xml_generator.completeElement('id', {}, unit.package_category_id)

        # If the order is not specified, then 1024 should be set as default.
        # With value of 1024 the group will be displayed at the very bottom of the list.
        display_order = unit.display_order if unit.display_order is not None else 1024
        self.xml_generator.completeElement('display_order', {}, str(display_order))

        self.xml_generator.completeElement('name', {}, unit.name)
        self._write_translated_fields('name', unit.translated_name)
        self.xml_generator.completeElement('description', {}, unit.description)
        self._write_translated_fields('description', unit.translated_description)

        self.xml_generator.startElement('grouplist', {})
        if unit.packagegroupids:
            for groupid in sorted(unit.packagegroupids):
                self.xml_generator.completeElement('groupid', {}, groupid)
        self.xml_generator.endElement('grouplist')
        self.xml_generator.endElement('category')

    def add_package_environment_unit_metadata(self, unit):
        """
        Write out the XML representation of a environment group unit

        :param unit: The environment group to publish
        :type unit: pulp_rpm.plugins.db.models.PackageEnvironment
        """
        self.xml_generator.startElement('environment', {})
        self.xml_generator.completeElement('id', {}, unit.package_environment_id)

        # If the order is not specified, then 1024 should be set as default.
        # With value of 1024 the group will be displayed at the very bottom of the list.
        display_order = unit.display_order if unit.display_order is not None else 1024
        self.xml_generator.completeElement('display_order', {}, str(display_order))

        self.xml_generator.completeElement('name', {}, unit.name)
        self._write_translated_fields('name', unit.translated_name)
        self.xml_generator.completeElement('description', {}, unit.description)
        self._write_translated_fields('description', unit.translated_description)

        self.xml_generator.startElement('grouplist', {})
        if unit.group_ids:
            for groupid in sorted(unit.group_ids):
                self.xml_generator.completeElement('groupid', {}, groupid)
        self.xml_generator.endElement('grouplist')

        self.xml_generator.startElement('optionlist', {})
        if unit.options:
            for option in sorted(unit.options):
                if option['default']:
                    attributes = {'default': 'true'}
                    self.xml_generator.completeElement('groupid', attributes, option['group'])
                else:
                    self.xml_generator.completeElement('groupid', {}, option['group'])

        self.xml_generator.endElement('optionlist')
        self.xml_generator.endElement('environment')

    def add_package_langpacks_unit_metadata(self, unit):
        """
        Write out the XML representation of a PackageLangpacks unit

        :param unit: The langpacks unit to publish
        :type unit: pulp_rpm.plugins.db.models.PackageLangpacks
        """
        self.xml_generator.startElement('langpacks', {})
        for match_dict in unit.matches:
            self.xml_generator.completeElement('match', match_dict, '')
        self.xml_generator.endElement('langpacks')
