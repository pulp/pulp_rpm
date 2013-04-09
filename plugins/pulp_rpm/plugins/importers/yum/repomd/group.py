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

PACKAGE_TAG = 'group'


def process_package_element(repo_id, element):
    packagelist = element.find('packagelist')
    conditional, default, mandatory, optional = _parse_packagelist(packagelist.findall('packagereq'))
    langonly = element.find('langonly') or element.find('lang_only')
    name, translated_name = _parse_translated(element.findall('name'))
    description, translated_description = _parse_translated(element.findall('description'))
    display_order = element.find('display_order')

    return models.PackageGroup.from_package_info({
        'conditional_package_names': conditional,
        'default': _parse_bool(element.find('default').text),
        'default_package_names': default,
        'description': description.text,
        # default of 1024 is from yum's own parsing of these objects
        'display_order': int(display_order.text) if display_order else 1024,
        'id': element.find('id').text,
        'langonly': langonly.text if langonly else None,
        'mandatory_package_names': mandatory,
        'name': name.text,
        'optional_package_names': optional,
        'repo_id': repo_id,
        'translated_description': translated_description,
        'translated_name': translated_name,
        'user_visible': _parse_bool(element.find('uservisible').text),
    })


def _parse_packagelist(packages):
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
    return text.strip().lower() == 'true'


def _parse_translated(items):
    value = ''
    translated_value = {}
    for item in items:
        if 'type' in item.attrib:
            translated_value[item.attrib['type']] = item
        else:
            value = item
    return value, translated_value
