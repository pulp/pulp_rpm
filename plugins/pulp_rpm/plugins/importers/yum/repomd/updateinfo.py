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

PACKAGE_TAG = 'update'


def process_package_element(element):
    ret = {
        'from': element.attrib['from'],
        'status': element.attrib['status'],
        'type': element.attrib['type'],
        'version': element.attrib['version'],
        'id': element.find('id').text,
        'title': element.find('title').text,
        'description': element.find('description').text,
        'issued': element.find('issued').attrib['date'],
        'references': map(_parse_reference, element.find('references') or []),
        'pkglist': map(_parse_collection, element.find('pkglist') or []),
    }

    for attr_name in ('rights', 'severity', 'summary', 'solution', 'release', 'pushcount'):
        child = element.find(attr_name)
        if child:
            ret[attr_name] = child.text
    for attr_name in ('updated',):
        child = element.find(attr_name)
        if child:
            ret[attr_name] = child.attrib[attr_name]
    return models.Errata.from_package_info(ret)


def _parse_reference(element):
    return {
        'id': element.attrib['id'],
        'href': element.attrib['href'],
        'type': element.attrib['type'],
        'title': element.text,
    }


def _parse_collection(element):
    ret = {
        'packages': map(_parse_package, element.findall('package')),
        'name': element.find('name').text,
    }
    # based on yum's parsing, this could be optional. See yum.update_md.UpdateNotice._parse_pkglist
    if 'short' in element.attrib:
        ret['short'] = element.attrib['short']

    return ret


def _parse_package(element):
    # looking at yum.update_md.UpdateNotice to see what attributes we can expect
    sum_element = element.find('sum')
    ret = {
        'arch': element.attrib['arch'],
        'name': element.attrib['name'],
        'epoch': element.attrib['epoch'],
        'version': element.attrib['version'],
        'release': element.attrib['release'],
        'src': element.attrib['src'],
        'filename': element.find('filename').text,
        'sum': (sum_element.attrib['type'], sum_element.text),
    }

    reboot_suggested = element.find('reboot_suggested')
    if reboot_suggested:
        ret['reboot_suggested'] = reboot_suggested.text

    return ret
