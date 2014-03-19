# -*- coding: utf-8 -*-

METADATA_FILE_NAME = 'other'

PACKAGE_TAG = 'package'


def process_package_element(element):
    """

    :param element:
    :type  element: xml.etree.ElementTree.Element
    :return:
    """
    version_element = element.find('version')
    unit_key = {
        'name': element.attrib['name'],
        'epoch': version_element.attrib['epoch'],
        'version': version_element.attrib['ver'],
        'release': version_element.attrib['rel'],
        'arch': element.attrib['arch'],
    }
    changelogs = _parse_changelogs(element.findall('changelog'))

    return unit_key, changelogs

def _parse_changelogs(elements):
    ret = []
    for element in elements:
        author = element.attrib['author']
        date = int(element.attrib['date'])
        text = element.text
        # this is the format the original importer used, so I'm blindly sticking with it.
        ret.append([date, author, text])

    return ret
