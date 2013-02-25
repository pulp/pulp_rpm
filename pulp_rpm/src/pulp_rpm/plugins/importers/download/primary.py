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

import gzip
from xml.etree.ElementTree import iterparse
#from xml.etree.cElementTree import iterparse


COMMON_SPEC_URL = 'http://linux.duke.edu/metadata/common'
RPM_SPEC_URL = 'http://linux.duke.edu/metadata/rpm'

PACKAGE_TAG = '{%s}package' % COMMON_SPEC_URL

NAME_TAG = '{%s}name' % COMMON_SPEC_URL
ARCH_TAG = '{%s}arch' % COMMON_SPEC_URL
VERSION_TAG = '{%s}version' % COMMON_SPEC_URL
CHECKSUM_TAG = '{%s}checksum' % COMMON_SPEC_URL
SUMMARY_TAG = '{%s}summary' % COMMON_SPEC_URL
DESCRIPTION_TAG = '{%s}description' % COMMON_SPEC_URL
PACKAGER_TAG = '{%s}packager' % COMMON_SPEC_URL
URL_TAG = '{%s}url' % COMMON_SPEC_URL
TIME_TAG = '{%s}time' % COMMON_SPEC_URL
SIZE_TAG = '{%s}size' % COMMON_SPEC_URL
LOCATION_TAG = '{%s}location' % COMMON_SPEC_URL
FORMAT_TAG = '{%s}format' % COMMON_SPEC_URL

FILE_TAG = '{%s}file' % COMMON_SPEC_URL

RPM_LICENSE_TAG = '{%s}license' % RPM_SPEC_URL
RPM_VENDOR_TAG = '{%s}vendor' % RPM_SPEC_URL
RPM_GROUP_TAG = '{%s}group' % RPM_SPEC_URL
RPM_BUILDHOST_TAG = '{%s}buildhost' % RPM_SPEC_URL
RPM_SOURCERPM_TAG = '{%s}sourcerpm' % RPM_SPEC_URL
RPM_HEADER_RANGE_TAG = '{%s}header-range' % RPM_SPEC_URL
RPM_PROVIDES_TAG = '{%s}provides' % RPM_SPEC_URL
RPM_REQUIRES_TAG = '{%s}requires' % RPM_SPEC_URL
RPM_ENTRY_TAG = '{%s}entry' % RPM_SPEC_URL

PACKAGE_INFO_SKEL = {'type': None,
                     'name': None,
                     'arch': None,
                     'version': None,
                     'release': None,
                     'epoch': None,
                     'checksum': {'algorithm': None, 'hex_digest': None},
                     'summary': None,
                     'description': None,
                     'changelog': None,
                     'build_time': None,
                     'url': None,
                     'time': None,
                     'size': None,
                     'relative_url_path': None}

PACKAGE_FORMAT_SKEL = {'vendor': None,
                       'license': None,
                       'group': None,
                       'header_range': {'start': None, 'end': None},
                       'build_host': None,
                       'requires': [],
                       'provides': [],
                       'files': []}

RPM_ENTRY_SKEL = {'name': None,
                  'version': None,
                  'release': None,
                  'epoch': None,
                  'flags': None}

FILE_INFO_SKEL = {'path': None}

# parser -----------------------------------------------------------------------

def primary_package_list_generator(primary_xml_handle):
    parser = iterparse(primary_xml_handle, events=('start', 'end'))
    xml_iterator = iter(parser)

    # get a hold of the root element so we can clear it
    # this prevents the entire parsed document from building up in memory
    root_element = xml_iterator.next()[1]

    for event, element in xml_iterator:
        if event != 'end' or element.tag != PACKAGE_TAG:
            continue

        root_element.clear()

        package_info = _process_package_element(element)
        yield package_info


def _process_package_element(package_element):
    package_info = PACKAGE_INFO_SKEL.copy()
    package_info['type'] = package_element.attrib['type']

    name_element = package_element.find(NAME_TAG)
    if name_element is not None:
        package_info['name'] = name_element.text

    arch_element = package_element.find(ARCH_TAG)
    if arch_element is not None:
        package_info['arch'] = arch_element.text

    version_element = package_element.find(VERSION_TAG)
    if version_element is not None:
        package_info['version'] = version_element.attrib['ver']
        package_info['release'] = version_element.attrib.get('rel', None)
        package_info['epoch'] = version_element.attrib.get('epoch', None)

    checksum_element = package_element.find(CHECKSUM_TAG)
    if checksum_element is not None:
        package_info['checksum']['algorithm'] = checksum_element.attrib['type']
        package_info['checksum']['hex_digest'] = checksum_element.text

    summary_element = package_element.find(SUMMARY_TAG)
    if summary_element is not None:
        package_info['summary'] = summary_element.text

    description_element = package_element.find(DESCRIPTION_TAG)
    if description_element is not None:
        package_info['description'] = description_element.text

    url_element = package_element.find(URL_TAG)
    if url_element is not None:
        package_info['url'] = url_element.text

    time_element = package_element.find(TIME_TAG)
    if time_element is not None:
        package_info['time'] = int(time_element.attrib['file'])
        package_info['build_time'] = int(time_element.attrib['build'])

    size_element = package_element.find(SIZE_TAG)
    if size_element is not None:
        package_info['size'] = int(size_element.attrib['package'])

    location_element = package_element.find(LOCATION_TAG)
    if location_element is not None:
        package_info['relative_url_path'] = location_element.attrib['href']

    format_element = package_element.find(FORMAT_TAG)
    #pprint(format_element.__dict__)
    package_info.update(_process_format_element(format_element))

    return package_info


def _process_format_element(format_element):
    package_format = PACKAGE_FORMAT_SKEL.copy()

    if format_element is None:
        return package_format

    vendor_element = format_element.find(RPM_VENDOR_TAG)
    if vendor_element is not None:
        package_format['vendor'] = None # XXX figure out which attrib this is

    license_element = format_element.find(RPM_LICENSE_TAG)
    if license_element is not None:
        package_format['license'] = license_element.text

    group_element = format_element.find(RPM_GROUP_TAG)
    if group_element is not None:
        package_format['group'] = group_element.text

    header_range_element = format_element.find(RPM_HEADER_RANGE_TAG)
    if header_range_element is not None:
        package_format['header_range']['start'] = int(header_range_element.attrib['start'])
        package_format['header_range']['end'] = int(header_range_element.attrib['end'])

    build_host_element = format_element.find(RPM_BUILDHOST_TAG)
    if build_host_element is not None:
        package_format['build_host'] = build_host_element.text

    provides_element = format_element.find(RPM_PROVIDES_TAG)
    if provides_element is not None:
        rpm_elements = [_process_rpm_entry_element(e) for e in provides_element.findall(RPM_ENTRY_TAG)]
        package_format['provides'].extend(rpm_elements)

    requires_element = format_element.find(RPM_REQUIRES_TAG)
    if requires_element is not None:
        rpm_elements = [_process_rpm_entry_element(e) for e in requires_element.findall(RPM_ENTRY_TAG)]
        package_format['requires'].extend(rpm_elements)

    package_format['files'].extend(_process_file_element(e) for e in format_element.findall(FILE_TAG))

    return package_format


def _process_rpm_entry_element(rpm_entry_element):
    rpm_entry = RPM_ENTRY_SKEL.copy()

    rpm_entry['name'] = rpm_entry_element.attrib['name']
    rpm_entry['version'] = rpm_entry_element.attrib.get('ver', None)
    rpm_entry['release'] = rpm_entry_element.attrib.get('rel', None)
    rpm_entry['epoch'] = rpm_entry_element.attrib.get('epoch', None)
    rpm_entry['flags'] = rpm_entry_element.attrib.get('flags', None)

    return rpm_entry


def _process_file_element(file_element):
    file_info = FILE_INFO_SKEL.copy()

    file_info['path'] = file_element.text

    return file_info

# testing ----------------------------------------------------------------------

def parse_primary(primary_xml_file_path):
    import resource
    from datetime import datetime
    from pprint import pprint

    if primary_xml_file_path.endswith('.gz'):
        primary_handle = gzip.open(primary_xml_file_path, 'r')
    else:
        primary_handle = open(primary_xml_file_path, 'r')

    usage = resource.getrusage(resource.RUSAGE_SELF)
    start_mem_usage = usage.ru_idrss + usage.ru_ixrss

    start_time = datetime.now()

    package_info_generator = primary_package_list_generator(primary_handle)

    for package_info in package_info_generator:
        #pprint(package_info)
        pass

    finish_time = datetime.now()

    usage = resource.getrusage(resource.RUSAGE_SELF)
    finish_mem_usage = usage.ru_idrss + usage.ru_ixrss

    print 'time elapsed: %s' % str(finish_time - start_time)
    print 'memory usage: %s' % str(finish_mem_usage - start_mem_usage)


if __name__ == '__main__':
    import sys
    primary_path = sys.argv[-1]
    #primary_path = '/Users/jasonconnor/Downloads/ebab889576b7c4300036a89f8d41014a10c28874b8e3842e7a7cc0c6b83e30a3-primary.xml.gz'
    parse_primary(primary_path)

