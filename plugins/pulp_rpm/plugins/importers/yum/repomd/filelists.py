# -*- coding: utf-8 -*-

METADATA_FILE_NAME = 'filelists'

PACKAGE_TAG = 'package'


def process_package_element(element):
    """
    Process one element from the filelists.xml file and return its parsed data.

    :param element: object representing an XML block for one package's file list
    :type  element: xml.etree.ElementTree.Element

    :return:    unit key and dictionary containing keys "file" and "dir" where
                values are full filesystem paths as strings.
    :rtype:     tuple(dict, dict)
    """
    version_element = element.find('version')
    unit_key = {
        'name': element.attrib['name'],
        'epoch': version_element.attrib['epoch'],
        'version': version_element.attrib['ver'],
        'release': version_element.attrib['rel'],
        'arch': element.attrib['arch'],
    }
    files = _sort_files_from_dirs(element.findall('file'))

    return unit_key, files


def _sort_files_from_dirs(elements):
    """
    For each "file" entry for a package, determine if it is a directory or not,
    and sort accordingly. This is for storage in Pulp's database directly on the
    RPM object.

    :param elements:    list of xml.etree.ElementTree.Element instances
    :type  elements:    list

    :return:    dictionary containing keys "file" and "dir" where
                values are full filesystem paths as strings.
    :rtype:     dict
    """
    files = []
    dirs = []
    for element in elements:
        if element.attrib.get('type') == 'dir':
            dirs.append(element.text)
        else:
            files.append(element.text)

    return {'file': files, 'dir': dirs}
