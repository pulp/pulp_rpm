"""Tests that verify download of content served by Pulp."""

import pytest

from pulp_rpm.tests.functional.constants import (
    CENTOS8_STREAM_BASEOS_URL,
    CENTOS8_STREAM_APPSTREAM_URL,
)


@pytest.mark.parallel
@pytest.mark.parametrize("url", [CENTOS8_STREAM_BASEOS_URL, CENTOS8_STREAM_APPSTREAM_URL])
def test_pulp_to_pulp(
    url,
    init_and_sync,
    rpm_publication_factory,
    rpm_distribution_factory,
    rpm_repository_version_api,
    distribution_base_url,
):
    """Verify whether content served by pulp can be synced.

    Do the following:

    1. Create, populate, publish, and distribute a repository.
    2. Sync other repository using as remote url,
    the distribution base_url from the previous repository.

    """
    repo, remote, task = init_and_sync(url=url, policy="on_demand", return_task=True)
    task_duration = task.finished_at - task.started_at
    waiting_time = task.started_at - task.pulp_created
    print(
        "\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(), service=task_duration.total_seconds()
        )
    )

    # Create a publication & distribution
    publication = rpm_publication_factory(repository=repo.pulp_href)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)

    # Create another repo pointing to distribution base_url
    repo2, remote2, task = init_and_sync(
        url=distribution_base_url(distribution.base_url), policy="on_demand", return_task=True
    )
    task_duration = task.finished_at - task.started_at
    waiting_time = task.started_at - task.pulp_created
    print(
        "\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(), service=task_duration.total_seconds()
        )
    )

    repo_ver = rpm_repository_version_api.read(repo.latest_version_href)
    repo2_ver = rpm_repository_version_api.read(repo2.latest_version_href)
    repo_summary = {k: v["count"] for k, v in repo_ver.content_summary.present.items()}
    repo2_summary = {k: v["count"] for k, v in repo2_ver.content_summary.present.items()}
    assert repo_summary == repo2_summary

    repo_summary = {k: v["count"] for k, v in repo_ver.content_summary.added.items()}
    repo2_summary = {k: v["count"] for k, v in repo2_ver.content_summary.added.items()}
    assert repo_summary == repo2_summary
