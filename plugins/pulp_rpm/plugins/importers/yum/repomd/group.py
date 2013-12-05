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

import logging

from pulp_rpm.common import models

_LOGGER = logging.getLogger(__name__)

GROUP_TAG = 'group'
CATEGORY_TAG = 'category'
ENVIRONMENT_TAG = 'environment'
METADATA_FILE_NAME = 'comps'
# this according to yum.comps.lang_attr
LANGUAGE_TAG = '{http://www.w3.org/XML/1998/namespace}lang'


def process_group_element(repo_id, element):
    """
    Process one XML block from comps.xml and return a models.PackageGroup instance

    :param repo_id: unique ID for the destination repository
    :type  repo_id  basestring
    :param element: object representing one "group" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.PackageGroup instance for the XML block
    :rtype:     pulp_rpm.common.models.PackageGroup
    """
    packagelist = element.find('packagelist')
    conditional, default, mandatory, optional = _parse_packagelist(packagelist.findall('packagereq'))
    langonly = element.find('langonly') or element.find('lang_only')
    name, translated_name = _parse_translated(element.findall('name'))
    description, translated_description = _parse_translated(element.findall('description'))
    display_order = element.find('display_order')
    # yum.comps.Group.parse suggests that this should default to False
    group_default = _parse_bool(element.find('default').text)\
        if element.find('default') is not None else False
    # yum.comps.Group.__init__ suggests that this should default to True
    user_visible = _parse_bool(element.find('uservisible').text)\
        if element.find('uservisible') is not None else True

    return models.PackageGroup.from_package_info({
        'conditional_package_names': conditional,
        'default': group_default,
        'default_package_names': default,
        'description': description,
        # default of 1024 is from yum's own parsing of these objects
        'display_order': int(display_order.text) if display_order else 1024,
        'id': element.find('id').text,
        'langonly': langonly.text if langonly else None,
        'mandatory_package_names': mandatory,
        'name': name,
        'optional_package_names': optional,
        'repo_id': repo_id,
        'translated_description': translated_description,
        'translated_name': translated_name,
        'user_visible': user_visible,
    })


def process_category_element(repo_id, element):
    """
    Process one XML block from comps.xml and return a models.PackageCategory instance

    :param repo_id: unique ID for the destination repository
    :type  repo_id  basestring
    :param element: object representing one "category" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.PackageCategory instance for the XML block
    :rtype:     pulp_rpm.common.models.PackageCategory
    """
    description, translated_description = _parse_translated(element.findall('description'))
    name, translated_name = _parse_translated(element.findall('name'))
    display_order = element.find('display_order')
    groups = element.find('grouplist').findall('groupid')

    return models.PackageCategory.from_package_info({
        'description': description,
        # default of 1024 is from yum's own parsing of these objects
        'display_order': int(display_order.text) if display_order is not None else 1024,
        'packagegroupids': [group.text for group in groups],
        'id': element.find('id').text,
        'name': name,
        'repo_id': repo_id,
        'translated_description': translated_description,
        'translated_name': translated_name,
    })


def process_environment_element(repo_id, element):
    """
    Process one XML block from comps.xml and return a models.PackageEnvironment instance

    :param repo_id: unique ID for the destination repository
    :type  repo_id  basestring
    :param element: object representing one "environment" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.PackageEnvironment instance for the XML block
    :rtype:     pulp_rpm.common.models.PackageEnvironment
    """
    description, translated_description = _parse_translated(element.findall('description'))
    name, translated_name = _parse_translated(element.findall('name'))
    display_order = element.find('display_order')
    groups = element.find('grouplist').findall('groupid')

    options = []
    for group in element.find('optionlist').findall('groupid'):
        default = group.attrib.get('default', False)
        options.append({'group': group.text, 'default': default})

    return models.PackageEnvironment.from_package_info({
        'description': description,
        # default of 1024 is from yum's own parsing of these objects
        'display_order': int(display_order.text) if display_order is not None else 1024,
        'group_ids': [group.text for group in groups],
        'id': element.find('id').text,
        'name': name,
        'repo_id': repo_id,
        'translated_description': translated_description,
        'translated_name': translated_name,
        'options': options
    })


def _parse_packagelist(packages):
    """
    For each "packagereq" entry for a group, sort it into a genre and parse
    its data into a package name and other possible values.

    :param packages:    list of xml.etree.ElementTree.Element instances
    :type  packages:    list

    :return:    tuple containing lists of package names in the order listed below
                in the "genres" dictionary. The "conditional" list contains tuples
                with package name, and then a requirements object
    :rtype:     tuple
    """
    genres = {
        'conditional': [],
        'default': [],
        'mandatory': [],
        'optional': [],
    }

    for package in packages:
        genre = package.attrib.get('type', 'mandatory')
        if genre == 'conditional':
            genres[genre].append((package.text, package.attrib.get('requires')))
        else:
            genres[genre].append(package.text)

    # using alphabetical order of keys to help return values in correct order
    return tuple(genres[key] for key in sorted(genres.keys()))


def _parse_bool(text):
    """
    returns boolean value True iff the text, when converted to lowercase, is
    exactly "true". Otherwise returns False

    :param text: text that represents a boolean value
    :type  text: basestring

    :return     True or False
    :rtype:     bool
    """
    return text.strip().lower() == 'true'


def _parse_translated(items):
    """
    one value will not have a "type", and it is the canonical "untranslated"
    value. Others are "translated" and have a specific type. This function sorts
    them.

    :param items:   iterable of elements representing a string value which is
                    possibly a translation
    :type  items:   iterable of xml.etree.ElementTree.Element

    :return:    tuple of the untranslated string value, and a dict where keys
                are "types" and values are translated versions of the original
                value
    """
    value = ''
    translated_value = {}
    for item in items:
        if LANGUAGE_TAG in item.attrib:
            translated_value[item.attrib[LANGUAGE_TAG]] = item.text
        else:
            value = item.text
    return value, translated_value
