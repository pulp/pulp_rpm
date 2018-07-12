# -*- coding: utf-8 -*-

import os

from pulp.server import util

from pulp_rpm.common import file_utils
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import utils


# primary.xml element tags -----------------------------------------------------
METADATA_FILE_NAME = 'primary'

COMMON_SPEC_URL = 'http://linux.duke.edu/metadata/common'
RPM_SPEC_URL = 'http://linux.duke.edu/metadata/rpm'


# primary.xml element tags -----------------------------------------------------
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
RPM_RECOMMENDS_TAG = '{%s}recommends' % RPM_SPEC_URL
RPM_ENTRY_TAG = '{%s}entry' % RPM_SPEC_URL

# package information dictionary -----------------------------------------------

# the package information dictionary is a combination of the PACKAGE_INFO_SKEL
# and PACKAGE_FORMAT_SKEL dictionaries
# all fields, along with their default values, are guaranteed to be there

PACKAGE_INFO_SKEL = {'type': None,
                     'name': None,
                     'arch': None,
                     'version': None,
                     'release': None,
                     'epoch': None,
                     'checksum': None,
                     'checksumtype': None,
                     'summary': None,
                     'description': None,
                     'changelog': None,
                     'build_time': None,
                     'url': None,
                     'time': None,
                     'size': None,
                     'filename': None,
                     'relative_url_path': None}

PACKAGE_FORMAT_SKEL = {'vendor': None,
                       'license': None,
                       'group': None,
                       'header_range': {'start': None, 'end': None},
                       'buildhost': None,
                       'requires': [],
                       'provides': [],
                       'sourcerpm': None,
                       'files': []}

# element processing methods ---------------------------------------------------


def process_package_element(package_element):
    """
    Process a parsed primary.xml package element into a model instance.

    In addition to parsing the data, this templatizes the raw XML that gets added.

    :param package_element: parsed primary.xml package element
    :return: package information dictionary
    :rtype: pulp_rpm.plugins.db.models.RPM
    """
    package_info = dict()

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
        checksum_type = util.sanitize_checksum_type(checksum_element.attrib['type'])
        package_info['checksumtype'] = checksum_type
        package_info['checksum'] = checksum_element.text

        # convert these to template targets that will be rendered at publish time
        checksum_element.text = models.RpmBase.CHECKSUM_TEMPLATE
        checksum_element.attrib['type'] = models.RpmBase.CHECKSUMTYPE_TEMPLATE

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
        href = location_element.attrib['href']
        base_url = None
        for attribute, value in location_element.items():
            if attribute == 'base' or attribute.endswith('}base'):
                base_url = value
        package_info['base_url'] = base_url
        filename = os.path.basename(href)
        package_info['relativepath'] = href
        package_info['filename'] = filename
        # we don't make any attempt to preserve the original directory structure
        # this element will end up being converted back to XML and stuffed into
        # the DB on the unit object, so this  is our chance to modify it.
        location_element.attrib['href'] = file_utils.make_packages_relative_path(filename)

    format_element = package_element.find(FORMAT_TAG)
    package_info.update(_process_format_element(format_element))

    if package_info['arch'].lower() == 'src':
        model = models.SRPM(**package_info)
    else:
        model = models.RPM(**package_info)
    # add the raw XML so it can be saved in the database later
    rpm_namespace = utils.Namespace('rpm', RPM_SPEC_URL)
    model.raw_xml = utils.element_to_raw_xml(package_element, [rpm_namespace], COMMON_SPEC_URL)
    return model


def _process_format_element(format_element):
    """
    Process a parsed primary.xml package format element (child element of
    package element) into a package format dictionary.

    :param format_element: parsed primary.xml package format element
    :return: package format dictionary
    :rtype: dict
    """
    package_format = dict()

    if format_element is None:
        return package_format

    vendor_element = format_element.find(RPM_VENDOR_TAG)
    if vendor_element is not None:
        package_format['vendor'] = None  # XXX figure out which attrib this is

    license_element = format_element.find(RPM_LICENSE_TAG)
    if license_element is not None:
        package_format['license'] = license_element.text

    group_element = format_element.find(RPM_GROUP_TAG)
    if group_element is not None:
        package_format['group'] = group_element.text

    header_range_element = format_element.find(RPM_HEADER_RANGE_TAG)
    if header_range_element is not None:
        package_format['header_range'] = dict()
        package_format['header_range']['start'] = int(header_range_element.attrib['start'])
        package_format['header_range']['end'] = int(header_range_element.attrib['end'])

    build_host_element = format_element.find(RPM_BUILDHOST_TAG)
    if build_host_element is not None:
        package_format['buildhost'] = build_host_element.text

    sourcerpm_element = format_element.find(RPM_SOURCERPM_TAG)
    if sourcerpm_element is not None:
        package_format['sourcerpm'] = sourcerpm_element.text

    provides_element = format_element.find(RPM_PROVIDES_TAG)
    if provides_element is not None:
        package_format['provides'] = \
            [_process_rpm_entry_element(e) for e in provides_element.findall(RPM_ENTRY_TAG)]

    requires_element = format_element.find(RPM_REQUIRES_TAG)
    if requires_element is not None:
        package_format['requires'] = \
            [_process_rpm_entry_element(e) for e in requires_element.findall(RPM_ENTRY_TAG)]

    recommends_element = format_element.find(RPM_RECOMMENDS_TAG)
    if recommends_element is not None:
        package_format['recommends'] = \
            [_process_rpm_entry_element(e) for e in recommends_element.findall(RPM_ENTRY_TAG)]

    package_format['files'] = \
        [_process_file_element(e) for e in format_element.findall(FILE_TAG)]

    return package_format


def _process_rpm_entry_element(rpm_entry_element):
    """
    Process a parsed RPM entry element (child elements of both provides and
    requires elements) into an RPM entry dictionary.

    :param rpm_entry_element: parsed RPM entry element
    :return: RPM entry dictionary
    :rtype: dict
    """
    rpm_entry = dict()

    rpm_entry['name'] = rpm_entry_element.attrib['name']
    rpm_entry['version'] = rpm_entry_element.attrib.get('ver', None)
    rpm_entry['release'] = rpm_entry_element.attrib.get('rel', None)
    rpm_entry['epoch'] = rpm_entry_element.attrib.get('epoch', None)
    rpm_entry['flags'] = rpm_entry_element.attrib.get('flags', None)

    return rpm_entry


def _process_file_element(file_element):
    """
    Process a parsed file element (child element of the files element) into a
    file information dictionary.

    :param file_element: parsed file element
    :return: file information dictionary
    :rtype: dict
    """
    file_info = dict()

    file_info['path'] = file_element.text

    return file_info
