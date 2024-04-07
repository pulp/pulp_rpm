"""Tests to test advisory conflict resolution functionality."""

from pulp_rpm.tests.functional.constants import (
    RPM_ADVISORY_DIFFERENT_PKGLIST_URL,
    RPM_ADVISORY_TEST_ID,
    RPM_UNSIGNED_FIXTURE_URL,
)


def test_two_advisories_same_id_to_repo(
    rpm_repository_api,
    rpm_advisory_api,
    rpm_repository_factory,
    init_and_sync,
    monitor_task,
    delete_orphans_pre,
):
    """
    Test when two different advisories with the same id are added to a repo.

    Should merge the two advisories into a single one.
    """
    # Setup
    repo_rpm_unsigned, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)
    repo_rpm_advisory_diffpkgs, _ = init_and_sync(url=RPM_ADVISORY_DIFFERENT_PKGLIST_URL)
    advisory_rpm_unsigned_href = (
        rpm_advisory_api.list(
            repository_version=repo_rpm_unsigned.latest_version_href,
            id=RPM_ADVISORY_TEST_ID,
        )
        .results[0]
        .pulp_href
    )
    advisory_rpm_advisory_diffpkgs_href = (
        rpm_advisory_api.list(
            repository_version=repo_rpm_advisory_diffpkgs.latest_version_href,
            id=RPM_ADVISORY_TEST_ID,
        )
        .results[0]
        .pulp_href
    )

    # Test advisory conflicts
    repo = rpm_repository_factory()

    data = {
        "add_content_units": [
            advisory_rpm_unsigned_href,
            advisory_rpm_advisory_diffpkgs_href,
        ]
    }
    response = rpm_repository_api.modify(repo.pulp_href, data)
    monitor_task(response.task)
    a_repo = rpm_repository_api.read(repo.pulp_href)

    duplicated_advisory_list = rpm_advisory_api.list(
        repository_version=a_repo.latest_version_href,
        id=RPM_ADVISORY_TEST_ID,
    ).results
    assert 1 == len(duplicated_advisory_list)
