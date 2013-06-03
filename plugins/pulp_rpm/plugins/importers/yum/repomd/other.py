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
