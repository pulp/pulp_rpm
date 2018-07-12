import gzip
import sys

from pulp.server.db.connection import get_collection
from pulp.server.db.migrations.lib import utils

if sys.version_info < (2, 7):
    from xml.etree import ElementTree as ET
else:
    from xml.etree import cElementTree as ET


_NAMESPACES = {
    'common': "http://linux.duke.edu/metadata/common",
    'rpm': 'http://linux.duke.edu/metadata/rpm',
}

# The unit metadata snippets miss header/encoding and namespace references
# which aren't included until publish time. This breaks the parsing.
_HEADER = ('<?mxl version="1.0" encoding="UTF-8"?>\n'
           '<metadata xmlns="http://linux.duke.edu/metadata/common" '
           'xmlns:rpm="http://linux.duke.edu/metadata/rpm">\n {}'
           '</metadata>\n')


def migrate_rpm(collection, unit):
    """
    Uncompress single rpm unit primary metadata and populate the unit recommends attribute
    accordingly.

    :param collection: a collection of RPM units
    :type collection: pymongo.collection.Collection
    :param unit: the RPM unit being migrated
    :type unit: dict
    """
    primary_xml = unit.get('repodata', {}).get('primary', '')
    primary_xml = _HEADER.format(gzip.zlib.decompress(primary_xml))
    root_element = ET.fromstring(primary_xml)
    delta = {}
    # the evr+flags fields are actually the attrib attribute of the entry node
    # <rpm:entry name="foo" epoch="0" version="3.14" release="pi" flags="EQ" />
    delta['recommends'] = [
        rpm_entry.attrib for rpm_entry in root_element.iterfind(
            './common:package/common:format/rpm:recommends/rpm:entry', _NAMESPACES)
    ]
    if delta['recommends']:
        # NOTE(performance): update just in case non-empty recommends; empty or None recommends
        # will be handled by the model
        collection.update_one({'_id': unit['_id']}, {'$set': delta})


def migrate(*args, **kwargs):
    """
    Populate the RPM unit recommends attribute.
    Migration can be safely re-run multiple times.

    :param args: unused
    :type args: list
    :param kwargs: unused
    type kwargs: dict
    """
    rpm_collection = get_collection('units_rpm')
    # select only units without the recommends attribute, fetch just the
    # 'repodata.primary' attribute; the _id is always included
    rpm_selection = rpm_collection.find(
        {'recommends': {'$exists': False}}, ['repodata.primary']).batch_size(100)
    total_rpm_units = rpm_selection.count()
    with utils.MigrationProgressLog('RPM', total_rpm_units) as progress_log:
        for rpm in rpm_selection:
            migrate_rpm(rpm_collection, rpm)
            progress_log.progress()
