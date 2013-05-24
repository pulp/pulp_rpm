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

METADATA_FILE_NAME = 'filelists'

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
    files = _sort_files_from_dirs(element.findall('file'))

    return unit_key, files


def _sort_files_from_dirs(elements):
    files = []
    dirs = []
    for element in elements:
        if element.attrib.get('type') == 'dir':
            dirs.append(element.text)
        else:
            files.append(element.text)

    return {'file': files, 'dir': dirs}