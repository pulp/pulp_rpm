from cStringIO import StringIO
import sys
import os

from pulp.server.db import connection

if sys.version < (2, 7):
    # We need the non-C implementation so we can shove a namespace into its internal data structure,
    # since in python 2.6, the register_namespace function wasn't present.
    import xml.etree.ElementTree as ET
else:
    import xml.etree.cElementTree as ET


RPM_NAMESPACE = 'http://linux.duke.edu/metadata/rpm'
PULP_PACKAGES_DIR = 'Packages'

# this is required because some of the pre-migration XML tags use the "rpm"
# namespace, which causes a parse error if that namespace isn't declared.
FAKE_XML = '<?xml version="1.0" encoding="%(encoding)s"?><faketag ' \
           'xmlns:rpm="%(namespace)s">%(xml)s</faketag>'


def migrate(*args, **kwargs):
    """
    Migrate RPMs and SRPMs location to new format "Packages/[a-z]/.*".

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    try:
        ET.register_namespace('rpm', RPM_NAMESPACE)
    except AttributeError:
        # python 2.6 doesn't have the register_namespace function
        ET._namespace_map[RPM_NAMESPACE] = 'rpm'

    db = connection.get_database()
    rpm_collection = db['units_rpm']
    srpm_collection = db['units_srpm']

    for rpm in rpm_collection.find({}, ['repodata', 'filename']):
        migrate_rpm_base(rpm_collection, rpm)
    for srpm in srpm_collection.find({}, ['repodata', 'filename']):
        migrate_rpm_base(srpm_collection, srpm)


def migrate_rpm_base(collection, unit):
    """
    Migrate RPMs or SRPMs primary repodata location to new schema.

    :param collection:  collection of RPM units
    :type  collection:  pymongo.collection.Collection
    :param unit:        the RPM unit being migrated
    :type  unit:        dict
    """
    delta = {}
    delta['repodata'] = fix_location(unit['repodata'], unit['filename'])

    collection.update_one({'_id': unit['_id']}, {'$set': delta})


def fix_location(repodata, filename):
    """
    Parse primary repodata and return repodata with location tag matching new publish schema.

    :param package_element: XML element with name "package" from primary.xml
    :type  package_element: xml.etree.ElementTree.Element
    :param filename:        the name of the RPM's file
    :type  filename:        basestring
    """
    faked_primary = fake_xml_element(repodata['primary'])
    primary = faked_primary.find('package')

    _update_location(primary, filename)

    return {
        'primary': remove_fake_element(element_to_text(faked_primary)),
        'other': repodata["other"],
        'filelists': repodata["filelists"],
    }


def _update_location(package_element, filename):
    """
    Update location tag to match new publish schema.

    :param package_element: XML element with name "package" from primary.xml
    :type  package_element: xml.etree.ElementTree.Element
    :param filename:        the name of the RPM's file
    :type  filename:        basestring
    """
    location_element = package_element.find('location')
    location_element.set('href', os.path.join(PULP_PACKAGES_DIR, filename[0].lower(), filename))


def fake_xml_element(repodata_snippet):
    """
    Wrap a snippet of xml in a fake element so it can be coerced to an ElementTree Element.

    :param repodata_snippet: Snippet of XML to be turn into an ElementTree Element
    :type  repodata_snippet: str

    :return: Parsed ElementTree Element containing the parsed repodata snippet
    :rtype:  xml.etree.ElementTree.Element
    """
    try:
        # make a guess at the encoding
        codec = 'UTF-8'
        repodata_snippet.encode(codec)
    except UnicodeEncodeError:
        # best second guess we have, and it will never fail due to the nature
        # of the encoding.
        codec = 'ISO-8859-1'
    fake_xml = FAKE_XML % {'encoding': codec, 'xml': repodata_snippet,
                           'namespace': RPM_NAMESPACE}
    # s/fromstring/phone_home/
    return ET.fromstring(fake_xml.encode(codec))


def remove_fake_element(xml_text, first_expected_name='package'):
    """
    Given XML text that results from data that ran through the fake_xml_element() function above,
    remove the beginning and ending "faketag" elements.

    :param xml_text:    XML that starts and ends with a <faketag> element
    :type  xml_text:    basestring
    :param first_expected_name: the name of the first element expected after the opening faketag
                                element. Defaults to 'package'.
    :type  first_expected_name: basestring

    :return:    new XML string
    :rtype:     basestring
    """
    start_index = xml_text.find('<' + first_expected_name)
    end_index = xml_text.rfind('</faketag')

    return xml_text[start_index:end_index]


def element_to_text(element):
    """
    Given an element, return the raw XML as a string.

    :param element: an element instance that should be written as XML text
    :type  element: xml.etree.ElementTree.Element

    :return:    XML text
    :rtype:     basestring
    """
    out = StringIO()
    tree = ET.ElementTree(element)
    tree.write(out, encoding='utf-8')
    return out.getvalue()
