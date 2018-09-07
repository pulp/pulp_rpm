# coding=utf-8
"""Constants for Pulp RPM plugin tests."""
from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)

RPM_CONTENT_PATH = urljoin(CONTENT_PATH, 'rpm/packages/')
"""The location of RPM packages on the content endpoint."""

UPDATERECORD_CONTENT_PATH = urljoin(CONTENT_PATH, 'rpm/updates/')
"""The location of RPM UpdateRecords on the content endpoint."""

RPM_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'rpm/')

RPM_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'rpm/')

RPM_SIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-signed/')
"""The URL to a repository with signed RPM packages."""

RPM_UNSIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-unsigned/')
"""The URL to a repository with unsigned RPM packages."""

RPM_FIXTURE_COUNT = 39  # 35 Packages + 4 UpdateRecord units
"""The total number of content units present in the standard repositories, i.e.
:data:`RPM_SIGNED_FIXTURE_URL` and :data:`RPM_UNSIGNED_FIXTURE_URL`.
"""

RPM_FIXTURE_CONTENT_SUMMARY = {'package': 35, 'update': 4}
"""The breakdown of how many of each type of content unit are present in the standard
repositories, i.e. :data:`RPM_SIGNED_FIXTURE_URL` and :data:`RPM_UNSIGNED_FIXTURE_URL`.
This matches the format output by the "content_summary" field on "../repositories/../versions/../".
"""

RPM_SIGNED_URL = urljoin(RPM_SIGNED_FIXTURE_URL, 'bear-4.1-1.noarch.rpm')
"""The path to a single signed RPM package."""

RPM_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FIXTURE_URL, 'bear-4.1-1.noarch.rpm')
"""The path to a single unsigned RPM package."""

RPM_PACKAGE_NAME = 'bear'
"""The name of one RPM package."""

RPM_UPDATED_UPDATEINFO_FIXTURE_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-updated-updateinfo/')
"""The URL to a repository containing UpdateRecords (Errata) with the same IDs as the ones
in the standard repositories, but with different metadata.

Note: This repository uses unsigned RPMs.
"""

RPM_UPDATERECORD_ID = 'RHEA-2012:0058'
"""The ID of an UpdateRecord (erratum).

The package contained on this erratum is defined by :data:`RPM_UPDATERECORD_RPM_NAME` and
the erratum is present in the standard repositories, i.e. :data:`RPM_SIGNED_FIXTURE_URL`
and :data:`RPM_UNSIGNED_FIXTURE_URL`.
"""

RPM_UPDATERECORD_RPM_NAME = 'gorilla'
"""The name of the RPM named by :data:`RPM_UPDATERECORD_ID`."""
