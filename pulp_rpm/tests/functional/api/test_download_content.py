"""Tests that verify download of content served by Pulp."""

import hashlib
from random import choice
from urllib.parse import urljoin

import pytest
import requests

from pulp_rpm.tests.functional.constants import RPM_UNSIGNED_FIXTURE_URL
from pulp_rpm.tests.functional.utils import (
    get_package_repo_path,
)
from pulpcore.client.pulp_rpm import RpmRpmPublication


@pytest.mark.parallel
def test_all(
    rpm_unsigned_repo_immediate,
    rpm_package_api,
    rpm_publication_api,
    rpm_distribution_factory,
    download_content_unit,
    gen_object_with_cleanup,
):
    """Verify whether content served by pulp can be downloaded.

    The process of publishing content is more involved in Pulp 3 than it
    was under Pulp 2. Given a repository, the process is as follows:

    1. Create a publication from the repository. (The latest repository
       version is selected if no version is specified.) A publication is a
       repository version plus metadata.
    2. Create a distribution from the publication. The distribution defines
       at which URLs a publication is available, e.g.
       ``http://example.com/content/foo/`` and
       ``http://example.com/content/bar/``.

    Do the following:

    1. Create, populate, publish, and distribute a repository.
    2. Select a random content unit in the distribution. Download that
       content unit from Pulp, and verify that the content unit has the
       same checksum when fetched directly from Pulp-Fixtures.
    """
    # Sync a Repository
    repo = rpm_unsigned_repo_immediate

    # Create a publication.
    publish_data = RpmRpmPublication(repository=repo.pulp_href)
    publication = gen_object_with_cleanup(rpm_publication_api, publish_data)

    # Create a distribution.
    distribution = rpm_distribution_factory(publication=publication.pulp_href)

    # Pick a content unit (of each type), and download it from both Pulp Fixtures…
    packages = rpm_package_api.list(repository_version=repo.latest_version_href)
    package_paths = [p.location_href for p in packages.results]
    unit_path = choice(package_paths)
    fixture_hash = hashlib.sha256(
        requests.get(urljoin(RPM_UNSIGNED_FIXTURE_URL, unit_path)).content
    ).hexdigest()

    # …and Pulp.
    pkg_path = get_package_repo_path(unit_path)
    content = download_content_unit(distribution.base_path, pkg_path)
    pulp_hash = hashlib.sha256(content).hexdigest()

    assert fixture_hash == pulp_hash
