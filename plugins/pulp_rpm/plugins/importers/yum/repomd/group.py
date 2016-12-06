# -*- coding: utf-8 -*-

import logging

from pulp_rpm.plugins.db import models


_LOGGER = logging.getLogger(__name__)

GROUP_TAG = 'group'
CATEGORY_TAG = 'category'
ENVIRONMENT_TAG = 'environment'
LANGPACKS_TAG = 'langpacks'
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
    :rtype:     pulp_rpm.plugins.db.models.PackageGroup
    """
    packagelist = element.find('packagelist')
    conditional, default, mandatory, optional = _parse_packagelist(
        packagelist.findall('packagereq'))
    langonly = element.find('langonly') or element.find('lang_only')
    name, translated_name = _parse_translated(element.findall('name'))
    description, translated_description = _parse_translated(element.findall('description'))
    display_order = element.find('display_order')
    # yum.comps.Group.parse suggests that this should default to False
    group_default = _parse_bool(element.find('default').text) \
        if element.find('default') is not None else False
    # yum.comps.Group.__init__ suggests that this should default to True
    user_visible = _parse_bool(element.find('uservisible').text) \
        if element.find('uservisible') is not None else True

    unit = models.PackageGroup()
    unit.conditional_package_names = conditional
    unit.default = group_default
    unit.default_package_names = default
    unit.description = description
    # default of 1024 is from yum's own parsing of these objects
    unit.display_order = int(display_order.text) if display_order else 1024
    unit.package_group_id = element.find('id').text
    unit.langonly = langonly.text if langonly else None
    unit.mandatory_package_names = mandatory
    unit.name = name
    unit.optional_package_names = optional
    unit.repo_id = repo_id
    unit.translated_description = translated_description
    unit.translated_name = translated_name
    unit.user_visible = user_visible

    return unit


def process_category_element(repo_id, element):
    """
    Process one XML block from comps.xml and return a models.PackageCategory instance

    :param repo_id: unique ID for the destination repository
    :type  repo_id  basestring
    :param element: object representing one "category" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.PackageCategory instance for the XML block
    :rtype:     pulp_rpm.plugins.db.models.PackageCategory
    """
    description, translated_description = _parse_translated(element.findall('description'))
    name, translated_name = _parse_translated(element.findall('name'))
    display_order = element.find('display_order')
    groups = element.find('grouplist').findall('groupid')

    unit = models.PackageCategory()
    unit.description = description
    # default of 1024 is from yum's own parsing of these objects
    unit.display_order = int(display_order.text) if display_order is not None else 1024
    unit.packagegroupids = [group.text for group in groups]
    unit.package_category_id = element.find('id').text
    unit.name = name
    unit.repo_id = repo_id
    unit.translated_description = translated_description
    unit.translated_name = translated_name
    return unit


def process_environment_element(repo_id, element):
    """
    Process one XML block from comps.xml and return a models.PackageEnvironment instance

    :param repo_id: unique ID for the destination repository
    :type  repo_id  basestring
    :param element: object representing one "environment" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.PackageEnvironment instance for the XML block
    :rtype:     pulp_rpm.plugins.db.models.PackageEnvironment
    """
    description, translated_description = _parse_translated(element.findall('description'))
    name, translated_name = _parse_translated(element.findall('name'))
    display_order = element.find('display_order')
    groups = element.find('grouplist').findall('groupid')

    options = []
    # The optionlist tag is not always present
    option_list = element.find('optionlist')
    if option_list is not None:
        for group in option_list.findall('groupid'):
            default = group.attrib.get('default', False)
            options.append({'group': group.text, 'default': default})

    unit = models.PackageEnvironment()
    unit.description = description
    # default of 1024 is from yum's own parsing of these objects
    unit.display_order = int(display_order.text) if display_order is not None else 1024
    unit.group_ids = [group.text for group in groups]
    unit.package_environment_id = element.find('id').text
    unit.name = name
    unit.repo_id = repo_id
    unit.translated_description = translated_description
    unit.translated_name = translated_name
    unit.options = options
    return unit


def process_langpacks_element(repo_id, element):
    """
    Process one XML block from comps.xml and return a models.PackageLangpacks instance

    :param repo_id: unique ID for the destination repository
    :type  repo_id  basestring
    :param element: object representing one "PackageLangpacks" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.PackageLangpacks instance for the XML block
    :rtype:     pulp_rpm.plugins.db.models.PackageLangpacks
    """
    unit = models.PackageLangpacks()
    unit.repo_id = repo_id

    for match in element.findall('match'):
        unit.matches.append({'install': match.get('install'), 'name': match.get('name')})

    return unit


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
