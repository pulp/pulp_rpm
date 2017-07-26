import sys
import gzip

from pulp.server.db import connection

if sys.version < (2, 7):
    # We need the non-C implementation so we can shove a namespace into its internal data structure,
    # since in python 2.6, the register_namespace function wasn't present.
    import xml.etree.ElementTree as ET
else:
    import xml.etree.cElementTree as ET

FAKE_XML_COMMON = '<?xml version="1.0" encoding="%(encoding)s"?><faketag ' \
                  'xmlns="%(common_namespace)s" xmlns:rpm="%(rpm_namespace)s">%(xml)s</faketag>'

COMMON_NAMESPACE = 'http://linux.duke.edu/metadata/common'
RPM_NAMESPACE = 'http://linux.duke.edu/metadata/rpm'

# primary.xml element tags -----------------------------------------------------
PACKAGE_TAG = '{%s}package' % COMMON_NAMESPACE

NAME_TAG = '{%s}name' % COMMON_NAMESPACE
ARCH_TAG = '{%s}arch' % COMMON_NAMESPACE
VERSION_TAG = '{%s}version' % COMMON_NAMESPACE
CHECKSUM_TAG = '{%s}checksum' % COMMON_NAMESPACE
SUMMARY_TAG = '{%s}summary' % COMMON_NAMESPACE
DESCRIPTION_TAG = '{%s}description' % COMMON_NAMESPACE
PACKAGER_TAG = '{%s}packager' % COMMON_NAMESPACE
URL_TAG = '{%s}url' % COMMON_NAMESPACE
TIME_TAG = '{%s}time' % COMMON_NAMESPACE
SIZE_TAG = '{%s}size' % COMMON_NAMESPACE
LOCATION_TAG = '{%s}location' % COMMON_NAMESPACE
FORMAT_TAG = '{%s}format' % COMMON_NAMESPACE

FILE_TAG = '{%s}file' % COMMON_NAMESPACE

RPM_LICENSE_TAG = '{%s}license' % RPM_NAMESPACE
RPM_GROUP_TAG = '{%s}group' % RPM_NAMESPACE
RPM_BUILDHOST_TAG = '{%s}buildhost' % RPM_NAMESPACE
RPM_SOURCERPM_TAG = '{%s}sourcerpm' % RPM_NAMESPACE
RPM_HEADER_RANGE_TAG = '{%s}header-range' % RPM_NAMESPACE
RPM_ENTRY_TAG = '{%s}entry' % RPM_NAMESPACE


def migrate(*args, **kwargs):
    """
    Update uploaded RPMs and SRPMs metadata to contain same data as if they were synced.
    This migration operates on all units which have, group and summary empty, this includes not
    only uploaded units.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    rpm_collection = db['units_rpm']
    srpm_collection = db['units_srpm']

    for rpm in rpm_collection.find({"group": None, "summary": None}):
        fix_metadata(rpm_collection, rpm)
    for srpm in srpm_collection.find({"group": None, "summary": None}):
        fix_metadata(srpm_collection, srpm)


def fix_metadata(collection, unit):
    """
    Updates metadata of given unit to corespond with it's xml_snippet.

    :param collection:  collection of RPM units
    :type  collection:  pymongo.collection.Collection
    :param unit: The unit to be fixed.
    :type  unit: RPM or SRPM
    """
    primary_xml_snippet = decompress_repodata(unit['repodata']['primary'])
    package_xml = fake_xml_element(primary_xml_snippet).find(PACKAGE_TAG)
    delta = process_package_element(unit, package_xml)

    collection.update_one({'_id': unit['_id']}, {'$set': delta})


def fake_xml_element(repodata_snippet):
    """
    Wrap a snippet of xml in a fake element so it can be coerced to an ElementTree Element

    :param repodata_snippet: Snippet of XML to be turn into an ElementTree Element
    :type  repodata_snippet: str

    :return: Parsed ElementTree Element containing the parsed repodata snippet
    :rtype:  xml.etree.ElementTree.Element
    """
    register_namespace('rpm', RPM_NAMESPACE)
    register_namespace('', COMMON_NAMESPACE)
    try:
        # make a guess at the encoding
        codec = 'UTF-8'
        repodata_snippet.encode(codec)
    except UnicodeEncodeError:
        # best second guess we have, and it will never fail due to the nature
        # of the encoding.
        codec = 'ISO-8859-1'
    except UnicodeDecodeError:
        # sometimes input contains non-ASCII characters and it is not in the unicode form
        # in this case the best guess is that it is encoded as UTF-8
        repodata_snippet = repodata_snippet.decode('UTF-8')
    fake_xml = FAKE_XML_COMMON % {'encoding': codec, 'xml': repodata_snippet,
                                  'rpm_namespace': RPM_NAMESPACE,
                                  'common_namespace': COMMON_NAMESPACE}
    # s/fromstring/phone_home/
    return ET.fromstring(fake_xml.encode(codec))


def check_builtin(module):
    """
    This decorator tries to return a function of the same name as f from the given module, and falls
    back to just returning f. This is useful for backporting builtin functions that don't exist in
    early versions of python.

    :param f:      function being decorated
    :type  f:      function
    :param module: The module that would contain f, if it exists in this implementation of Python
    :type  module: module
    :return:       builtin function if found, else f
    """
    def wrap(f):
        return getattr(module, f.__name__, f)
    return wrap


@check_builtin(ET)
def register_namespace(prefix, uri):
    """
    Adapted from xml.etree.ElementTree.register_namespace as implemented
    in Python 2.7.

    This implementation makes no attempt to remove other namespaces. It appears
    that there is a race condition in the python 2.7 stdlib pure python
    implementation. For our purposes, we don't need to be concerned about
    unregistering a namespace or URI, so we can let them remain unless
    overwritten.

    :param prefix:  namespace prefix
    :param uri:     namespace URI. Tags and attributes in this namespace will be
                    serialized with the given prefix, if at all possible.
    """
    ET._namespace_map[uri] = prefix


def process_package_element(unit, package_element):
    """
    Process a parsed primary.xml package element into a model instance.

    In addition to parsing the data, this templatizes the raw XML that gets added.

    :param            unit: THe unit to be updated.
    :param package_element: parsed primary.xml package element
    :return: package information dictionary
    :rtype: pulp_rpm.plugins.db.models.RPM
    """

    delta = dict()

    summary_element = package_element.find(SUMMARY_TAG)
    if summary_element is not None:
        delta['summary'] = summary_element.text

    description_element = package_element.find(DESCRIPTION_TAG)
    if description_element is not None and 'description' not in unit:
        delta['description'] = description_element.text

    time_element = package_element.find(TIME_TAG)
    if time_element is not None:
        if 'time' not in unit:
            delta['time'] = int(time_element.attrib['file'])
        if 'build_time' not in unit:
            delta['build_time'] = int(time_element.attrib['build'])

    size_element = package_element.find(SIZE_TAG)
    if size_element is not None and 'size' not in unit:
        delta['size'] = int(size_element.attrib['package'])

    format_element = package_element.find(FORMAT_TAG)
    delta.update(_process_format_element(unit, format_element))

    return delta


def _process_format_element(unit, format_element):
    """
    Process a parsed primary.xml package format element (child element of
    package element) into a package format dictionary.

    :param            unit: THe unit to be updated.
    :param format_element: parsed primary.xml package format element
    :return: package format dictionary
    :rtype: dict
    """
    delta = dict()

    if format_element is None:
        return delta

    license_element = format_element.find(RPM_LICENSE_TAG)
    if license_element is not None and 'license' not in unit:
        delta['license'] = license_element.text

    group_element = format_element.find(RPM_GROUP_TAG)
    if group_element is not None:
        delta['group'] = group_element.text

    header_range_element = format_element.find(RPM_HEADER_RANGE_TAG)
    if header_range_element is not None and not unit.get('header_range'):
        delta['header_range'] = dict()
        delta['header_range']['start'] = int(header_range_element.attrib['start'])
        delta['header_range']['end'] = int(header_range_element.attrib['end'])

    build_host_element = format_element.find(RPM_BUILDHOST_TAG)
    if build_host_element is not None and 'buildhost' not in unit:
        delta['buildhost'] = build_host_element.text

    sourcerpm_element = format_element.find(RPM_SOURCERPM_TAG)
    if sourcerpm_element is not None and 'sourcerpm' not in unit:
        delta['sourcerpm'] = sourcerpm_element.text

    return delta


def decompress_repodata(repodata):
    """
    Decompress repodata.

    :param repodata: The commpressed metadata.
    :type  repodata: str

    :return: requested xml snippet
    :rtype:  unicode
    """
    return gzip.zlib.decompress(repodata).decode('utf-8')
