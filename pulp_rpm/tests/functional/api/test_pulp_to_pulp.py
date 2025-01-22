"""Tests that verify download of content served by Pulp."""

import pytest

from pulp_rpm.tests.functional.constants import DOWNLOAD_POLICIES
from pulpcore.client.pulp_rpm import RpmRpmPublication


@pytest.mark.parallel
@pytest.mark.parametrize("policy", DOWNLOAD_POLICIES)
def test_pulp_pulp_sync(
    policy,
    init_and_sync,
    distribution_base_url,
    rpm_repository_version_api,
    rpm_publication_api,
    rpm_distribution_factory,
    gen_object_with_cleanup,
):
    """Verify whether content served by Pulp can be synced.

    The initial sync to Pulp is one of many different download policies, the second sync is
    immediate in order to exercise downloading all of the files.

    Do the following:

    1. Create, populate, publish, and distribute a repository.
    2. Sync other repository using as remote url,
    the distribution base_url from the previous repository.

    """
    repo, remote = init_and_sync(policy=policy)

    # Create a publication.
    publish_data = RpmRpmPublication(
        repository=repo.pulp_href,
        checksum_type="sha512",
    )
    publication = gen_object_with_cleanup(rpm_publication_api, publish_data)

    # Create a distribution.
    distribution = rpm_distribution_factory(publication=publication.pulp_href)

    # Create another repo pointing to distribution base_url
    # Should this second policy always be "immediate"?
    repo2, remote2 = init_and_sync(
        url=distribution_base_url(distribution.base_url), policy="immediate"
    )
    repo_ver = rpm_repository_version_api.read(repo.latest_version_href)
    summary = {k: v["count"] for k, v in repo_ver.content_summary.present.items()}
    repo_ver2 = rpm_repository_version_api.read(repo2.latest_version_href)
    summary2 = {k: v["count"] for k, v in repo_ver2.content_summary.present.items()}
    assert summary == summary2

    added = {k: v["count"] for k, v in repo_ver.content_summary.added.items()}
    added2 = {k: v["count"] for k, v in repo_ver2.content_summary.added.items()}
    assert added == added2
