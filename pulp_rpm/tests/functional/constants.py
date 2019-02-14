# coding=utf-8
"""Constants for Pulp RPM plugin tests."""
from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH,
)

DRPM_UNSIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm-unsigned/')
"""The URL to a repository with unsigned DRPM packages."""

RPM_PACKAGE_CONTENT_NAME = 'rpm.package'

RPM_UPDATE_CONTENT_NAME = 'rpm.update'

RPM_ALT_LAYOUT_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-alt-layout/')
"""The URL to a signed RPM repository. See :data:`RPM_SIGNED_FIXTURE_URL`."""

RPM_CONTENT_PATH = urljoin(CONTENT_PATH, 'rpm/packages/')
"""The location of RPM packages on the content endpoint."""

RPM_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'rpm/rpm/')

RPM_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'rpm/rpm/')

RPM_SIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-signed/')
"""The URL to a repository with signed RPM packages."""

RPM_SHA512_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-with-sha-512/')
"""The URL to an RPM repository with sha512 checksum."""

RPM_UNSIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-unsigned/')
"""The URL to a repository with unsigned RPM packages."""

RPM_PACKAGES_COUNT = 35
"""The number of packages available at
:data:`RPM_SIGNED_FIXTURE_URL` and :data:`RPM_UNSIGNED_FIXTURE_URL`
"""

RPM_UPDATE_COUNT = 4
"""The number of updated record units."""

RPM_FIXTURE_SUMMARY = {
    RPM_PACKAGE_CONTENT_NAME: RPM_PACKAGES_COUNT,
    RPM_UPDATE_CONTENT_NAME: RPM_UPDATE_COUNT
}
"""The breakdown of how many of each type of content unit are present in the
standard repositories, i.e. :data:`RPM_SIGNED_FIXTURE_URL` and
:data:`RPM_UNSIGNED_FIXTURE_URL`.  This matches the format output by the
"content_summary" field on "../repositories/../versions/../".
"""

RPM_LONG_UPDATEINFO_FIXTURE_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-long-updateinfo/'
)
"""The URL to RPM with a long updateinfo.xml."""

RPM_PACKAGE_DATA = {
    'name': 'bear',
    'epoch': '0',
    'version': '4.1',
    'release': '1',
    'arch': 'noarch',
    'description': 'A dummy package of bear',
    'summary': 'A dummy package of bear',
    'rpm_license': 'GPLv2',
    'rpm_group': 'Internet/Applications',
    'rpm_vendor': '',
    # TODO: Complete this information once we figure out how to serialize
    # everything nicely
}
"""The metadata for one RPM package."""

RPM_PACKAGE_NAME = '{}'.format(RPM_PACKAGE_DATA['name'])
"""The name of one RPM package."""

RPM_PACKAGE_FILENAME = '{}-{}-{}.{}.rpm'.format(
    RPM_PACKAGE_DATA['name'],
    RPM_PACKAGE_DATA['version'],
    RPM_PACKAGE_DATA['release'],
    RPM_PACKAGE_DATA['arch'],
)
"""The filename of one RPM package."""

RPM_REFERENCES_UPDATEINFO_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-references-updateinfo/'
)
"""The URL to a repository with ``updateinfo.xml`` containing references.

This repository includes errata with reference element (0, 1 or 2 references)
and without it.
"""

RPM_RICH_WEAK_FIXTURE_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-richnweak-deps/'
)
"""The URL to an RPM repository with weak and rich dependencies."""

RPM_SIGNED_URL = urljoin(RPM_SIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)
"""The path to a single signed RPM package."""

RPM_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)
"""The path to a single unsigned RPM package."""

RPM_UPDATED_UPDATEINFO_FIXTURE_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-updated-updateinfo/'
)
"""The URL to a repository containing UpdateRecords (Errata) with the same IDs
as the ones in the standard repositories, but with different metadata.

Note: This repository uses unsigned RPMs.
"""

RPM_UPDATERECORD_ID = 'RHEA-2012:0058'
"""The ID of an UpdateRecord (erratum).

The package contained on this erratum is defined by
:data:`RPM_UPDATERECORD_RPM_NAME` and the erratum is present in the standard
repositories, i.e. :data:`RPM_SIGNED_FIXTURE_URL` and
:data:`RPM_UNSIGNED_FIXTURE_URL`.
"""

RPM_UPDATERECORD_RPM_NAME = 'gorilla'
"""The name of the RPM named by :data:`RPM_UPDATERECORD_ID`."""

RPM_WITH_NON_ASCII_NAME = 'rpm-with-non-ascii'

RPM_WITH_NON_ASCII_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-non-ascii/{}-1-1.fc25.noarch.rpm'.format(RPM_WITH_NON_ASCII_NAME)
)
"""The URL to an RPM with non-ascii metadata in its header."""

RPM_WITH_NON_UTF_8_NAME = 'rpm-with-non-utf-8'

RPM_WITH_NON_UTF_8_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-non-utf-8/{}-1-1.fc25.noarch.rpm'.format(RPM_WITH_NON_UTF_8_NAME)
)
"""The URL to an RPM with non-UTF-8 metadata in its header."""

SRPM_UNSIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-unsigned/')
"""The URL to a repository with unsigned SRPM packages."""

UPDATERECORD_CONTENT_PATH = urljoin(CONTENT_PATH, 'rpm/updates/')
"""The location of RPM UpdateRecords on the content endpoint."""
