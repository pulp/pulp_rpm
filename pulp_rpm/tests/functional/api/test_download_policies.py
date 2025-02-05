"""Tests for Pulp`s download policies."""

import pytest

from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_SUMMARY,
    DOWNLOAD_POLICIES,
)
from pulpcore.client.pulp_rpm import RpmRpmPublication


@pytest.mark.parametrize("download_policy", DOWNLOAD_POLICIES)
def test_download_policies(
    download_policy,
    init_and_sync,
    rpm_repository_version_api,
    rpm_publication_api,
    gen_object_with_cleanup,
    delete_orphans_pre,
    get_content_summary,
):
    """Sync repositories with the different ``download_policy``.

    Do the following:

    1. Create a repository, and a remote.
    2. Sync the remote.
    3. Assert that repository version is not None.
    4. Assert that the correct number of possible units to be downloaded
       were shown.
    5. Sync again with the same remote.
    6. Assert that the latest repository version did not change.
    7. Assert that the same number of units are shown, and after the
       second sync no extra units should be shown, since the same remote
       was synced again.
    8. Publish repository synced with lazy ``download_policy``.
    """
    # Step 1, 2
    repo, remote = init_and_sync(policy=download_policy)

    # Step 3, 4
    assert repo.latest_version_href.endswith("/1/")
    content_summary = get_content_summary(repo)
    assert content_summary["present"] == RPM_FIXTURE_SUMMARY
    assert content_summary["added"] == RPM_FIXTURE_SUMMARY

    # Step 5
    latest_version_href = repo.latest_version_href
    repo, remote = init_and_sync(repository=repo, remote=remote)

    # Step 6, 7
    assert latest_version_href == repo.latest_version_href
    content_summary = get_content_summary(repo)
    assert content_summary["present"] == RPM_FIXTURE_SUMMARY

    # Step 8
    publish_data = RpmRpmPublication(repository=repo.pulp_href)
    publication = gen_object_with_cleanup(rpm_publication_api, publish_data)

    assert publication.repository is not None
    assert publication.repository_version is not None
