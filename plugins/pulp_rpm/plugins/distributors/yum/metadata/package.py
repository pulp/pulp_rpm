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
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

"""
This module is used for generating all metadata related to package groups and categories
"""
import os
from xml.etree import ElementTree

from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    MetadataFileContext, REPO_DATA_DIR_NAME)
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

PACKAGE_XML_FILE_NAME = 'comps.xml'


class PackageXMLFileContext(MetadataFileContext):
    """
    The PackageXMLFileContext is used to generate the comps.xml file used in yum repositories
    for storing information about package categories and package groups
    """

    def __init__(self, working_dir):
        """
        Initialize and set the file where the metadata is being saved.

        :param working_dir: root working directory where the repo is being generated.
        :type  working_dir: str
        """

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, PACKAGE_XML_FILE_NAME)
        super(PackageXMLFileContext, self).__init__(metadata_file_path)

    def _write_root_tag_open(self):
        """
        Write the opening tag for the root element of a given metadata XML file.
        """

        updates_element = ElementTree.Element('comps')
        bogus_element = ElementTree.SubElement(updates_element, '')

        updates_tags_string = ElementTree.tostring(updates_element, 'utf-8')
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = updates_tags_string.split(bogus_tag_string, 1)

        doctype = u'<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">'
        self.metadata_file_handle.write(unicode(doctype + '\n' + opening_tag))

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(unicode(closing_tag + '\n'))

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_package_group_unit_metadata(self, group_unit):
        """
        Write out the XML representation of a group

        :param group_unit: AssociatedUnit of the group to publish
        :type group_unit: AssociatedUnit
        """
        group_element = ElementTree.Element('group')
        ElementTree.SubElement(group_element, 'id').text = group_unit.unit_key['id']
        ElementTree.SubElement(group_element, 'uservisible').text = \
            str(group_unit.metadata['user_visible']).lower()
        ElementTree.SubElement(group_element, 'display_order').text = \
            str(group_unit.metadata['display_order'])

        if 'langonly' in group_unit.metadata:
            ElementTree.SubElement(group_element, 'langonly').text = \
                group_unit.metadata['langonly']
        ElementTree.SubElement(group_element, 'name').text = \
            group_unit.metadata['name']
        if 'translated_name' in group_unit.metadata and group_unit.metadata['translated_name']:
            for key in group_unit.metadata['translated_name']:
                ElementTree.SubElement(group_element, 'name',
                                       {'xml:lang': key}).text = \
                    group_unit.metadata['translated_name'][key]
        ElementTree.SubElement(group_element, 'description').text = \
            group_unit.metadata['description']
        if 'translated_description' in group_unit.metadata and \
                group_unit.metadata['translated_description']:
            for key in group_unit.metadata['translated_description']:
                ElementTree.SubElement(group_element, 'description',
                                       {'xml:lang': key}).text = \
                    group_unit.metadata['translated_description'][key]

        package_list_element = ElementTree.SubElement(group_element, 'packagelist')
        if 'mandatory_package_names' in group_unit.metadata and \
            group_unit.metadata['mandatory_package_names']:
            for pkg in sorted(group_unit.metadata['mandatory_package_names']):
                ElementTree.SubElement(package_list_element, 'packagereq',
                                       {'type': 'mandatory'}).text = pkg
        if 'default_package_names' in group_unit.metadata and \
            group_unit.metadata['default_package_names']:
            for pkg in sorted(group_unit.metadata['default_package_names']):
                ElementTree.SubElement(package_list_element, 'packagereq',
                                       {'type': 'default'}).text = pkg
        if 'optional_package_names' in group_unit.metadata and \
            group_unit.metadata['optional_package_names']:
            for pkg in sorted(group_unit.metadata['optional_package_names']):
                ElementTree.SubElement(package_list_element, 'packagereq',
                                       {'type': 'optional'}).text = pkg
        if 'conditional_package_names' in group_unit.metadata and \
            group_unit.metadata['conditional_package_names']:
            for pkg_name, value in group_unit.metadata['conditional_package_names']:
                ElementTree.SubElement(package_list_element, 'packagereq',
                                       {'type': 'conditional',
                                        'requires': value}).text = pkg_name

        group_element_string = ElementTree.tostring(group_element, 'utf-8')
        _LOG.debug('Writing package_group unit metadata:\n' + group_element_string)
        self.metadata_file_handle.write(group_element_string)

    def add_package_category_unit_metadata(self, unit):
        """
        Write out the XML representation of a category unit

        :param group_unit: AssociatedUnit of the category o publish
        :type group_unit: AssociatedUnit
        """
        category_element = ElementTree.Element('category')
        category_id = unit.unit_key["id"]
        if category_id is None:
            category_id = unit.metadata['id']
        ElementTree.SubElement(category_element, 'id').text = category_id
        ElementTree.SubElement(category_element, 'display_order').text = \
            str(unit.metadata['display_order'])
        ElementTree.SubElement(category_element, 'name').text = \
            unit.metadata['name']
        if 'translated_name' in unit.metadata and unit.metadata['translated_name']:
            it = iter(sorted(unit.metadata['translated_name'].iteritems()))
            for pair in it:
                ElementTree.SubElement(category_element, 'name', {'xml:lang': pair[0]}).text = \
                    pair[1]
        ElementTree.SubElement(category_element, 'description').text = \
            unit.metadata['description']
        if 'translated_description' in unit.metadata and unit.metadata['translated_description']:
            it = iter(sorted(unit.metadata['translated_description'].iteritems()))
            for pair in it:
                ElementTree.SubElement(category_element, 'description', {'xml:lang': pair[0]}).text = \
                    pair[1]

        group_list_element = ElementTree.SubElement(category_element, 'grouplist')
        if 'packagegroupids' in unit.metadata and unit.metadata['packagegroupids']:
            for groupid in sorted(unit.metadata['packagegroupids']):
                ElementTree.SubElement(group_list_element, 'groupid').text = groupid

        #Write out the category xml to the file
        category_element_string = ElementTree.tostring(category_element, encoding='utf-8')
        _LOG.debug('Writing package_group unit metadata:\n' + category_element_string)
        self.metadata_file_handle.write(category_element_string)
