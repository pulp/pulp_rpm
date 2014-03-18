# -*- coding: utf-8 -*-

from xml.etree import cElementTree as ET

from pulp.plugins.types import database as types_db
from pulp.server.db import connection

from pulp_rpm.plugins.db.models import RPM, SRPM
from pulp_rpm.plugins.importers.yum import utils
from pulp_rpm.plugins.importers.yum.repomd import primary

# this is required because some of the pre-migration XML tags use the "rpm"
# namespace, which causes a parse error if that namespace isn't declared.
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
        utils.strip_ns(fake_element)
        primary_element = fake_element.find('package')
        format_element = primary_element.find('format')
        provides_element = format_element.find('provides')
        requires_element = format_element.find('requires')

        # add these attributes, which we previously didn't track in the DB.
        package['size'] = int(primary_element.find('size').attrib['package'])
        if type_id == RPM.TYPE:
            package['sourcerpm'] = format_element.find('sourcerpm').text
            package['summary'] = primary_element.find('summary').text

        # re-parse provides and requires. The format changed from 2.1, and the
        # 2.1 upload workflow was known to produce invalid data for these fields
        package['provides'] = map(primary._process_rpm_entry_element, provides_element.findall('entry')) if provides_element else []
        package['requires'] = map(primary._process_rpm_entry_element, requires_element.findall('entry')) if requires_element else []

        collection.save(package, safe=True)


if __name__ == '__main__':
    connection.initialize()
    migrate()
