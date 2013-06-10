# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from xml.etree import cElementTree as ET

from pulp.plugins.types import database as types_db
from pulp.server.db import connection

from pulp_rpm.common.models import RPM, SRPM
from pulp_rpm.plugins.importers.yum.repomd import packages

# this is required because some of the pre-migration XML tags use the "rpm"
# namespace, which causes a parse error if that namespace isn't declared.
from pulp_rpm.yum_plugin import util

FAKE_XML = '<?xml version="1.0" encoding="%(encoding)s"?><faketag xmlns:rpm="http://pulpproject.org">%(xml)s</faketag>'


def migrate(*args, **kwargs):
    for type_id in (RPM.TYPE, SRPM.TYPE):
        _migrate_collection(type_id)


def _migrate_collection(type_id):
    collection = types_db.type_units_collection(type_id)
    for package in collection.find():
        # grab the raw XML and parse it into the elements we'll need later
        try:
            # make a guess at the encoding
            codec = 'UTF-8'
            text = package['repodata']['primary'].encode(codec)
        except UnicodeEncodeError:
            # best second guess we have, and it will never fail due to the nature
            # of the encoding.
            codec = 'ISO-8859-1'
            text = package['repodata']['primary'].encode(codec)
        fake_xml = FAKE_XML % {'encoding': codec, 'xml': package['repodata']['primary']}
        fake_element = ET.fromstring(fake_xml.encode(codec))
        packages.strip_ns(fake_element)
        primary_element = fake_element.find('package')
        format_element = primary_element.find('format')

        # add these attributes, which we previously didn't track in the DB.
        package['size'] = int(primary_element.find('size').attrib['package'])
        if type_id == RPM.TYPE:
            package['sourcerpm'] = format_element.find('sourcerpm').text
            package['summary'] = primary_element.find('summary').text

        # re-generate the raw XML without the pesky "rpm" namespace
        package['repodata']['primary'] = packages.element_to_raw_xml(primary_element)

        # re-format provides
        package['provides'] = map(_reformat_provide_or_require, package.get('provides', []))
        package['requires'] = map(_reformat_provide_or_require, package.get('requires', []))

        collection.save(package, safe=True)


def _reformat_provide_or_require(old_representation):
    """
    2.1 provide statements have the form: [ "name", "flags", [ "epoch", "version", "release"]]

    :param old_representation:
    :return:
    """
    if isinstance(old_representation, dict):
        return old_representation
    return {
        'name': old_representation[0],
        'flags': old_representation[1],
        'epoch': old_representation[2][0],
        'version': old_representation[2][1],
        'release': old_representation[2][2],
    }


if __name__ == '__main__':
    connection.initialize()
    migrate()
