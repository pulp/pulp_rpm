"""Tests for the retention policy feature of repositories."""

import pytest

from collections import defaultdict

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_PACKAGE,
    RPM_FIXTURE_SUMMARY,
    RPM_PACKAGE_COUNT,
    RPM_MODULAR_PACKAGE_COUNT,
    RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL,
    RPM_MODULAR_STATIC_FIXTURE_SUMMARY,
)
from pulpcore.client.pulp_rpm.exceptions import ApiException


def test_sync_with_retention(
    delete_orphans_pre,
    init_and_sync,
    rpm_repository_api,
    rpm_repository_version_api,
    rpm_package_api,
    monitor_task,
    get_content_summary,
):
    """Verify functionality with sync.

    Do the following:

    1. Create a repository, and a remote.
    2. Sync the remote.
    3. Assert that the correct number of units were added and are present
       in the repo.
    4. Change the "retain_package_versions" on the repository to 1 (retain the latest
       version only).
    5. Sync the remote one more time.
    6. Assert that repository version is different from the previous one.
    7. Assert the repository version we end with has only one version of each package.
    """
    repo, remote, task = init_and_sync(policy="on_demand", optimize=False, return_task=True)
    summary = get_content_summary(repo)

    # Test that, by default, everything is retained / nothing is tossed out.
    assert summary["present"] == RPM_FIXTURE_SUMMARY
    assert summary["added"] == RPM_FIXTURE_SUMMARY

    # Test that the # of packages processed is correct
    reports = get_progress_reports_by_code(task)
    assert reports["sync.parsing.packages"].total == RPM_PACKAGE_COUNT

    # Set the retention policy to retain only 1 version of each package
    repo_data = repo.to_dict()
    repo_data.update({"retain_package_versions": 1})
    monitor_task(rpm_repository_api.update(repo.pulp_href, repo_data).task)
    repo = rpm_repository_api.read(repo.pulp_href)

    repo, remote, task = init_and_sync(
        repository=repo, remote=remote, optimize=False, return_task=True
    )

    # Test that only one version of each package is present
    content = rpm_package_api.list(repository_version=repo.latest_version_href).results
    assert check_retention_policy(content, 1)
    # Test that (only) 4 RPMs were removed (no advisories etc. touched)
    version = rpm_repository_version_api.read(repo.latest_version_href)
    removed = {k: v["count"] for k, v in version.content_summary.removed.items()}
    assert removed == {PULP_TYPE_PACKAGE: 4}
    # Test that the versions that were removed are the versions we expect.
    content = rpm_package_api.list(repository_version_removed=repo.latest_version_href).results
    versions = versions_for_packages(content)
    assert versions == {"duck": ["0.6", "0.7"], "kangaroo": ["0.2"], "walrus": ["0.71"]}, versions
    # Test that the number of packages processed is correct (doesn't include older ones)
    reports = get_progress_reports_by_code(task)
    assert reports["sync.parsing.packages"].total == RPM_PACKAGE_COUNT
    assert reports["sync.skipped.packages"].total == 4


def test_sync_with_retention_and_modules(
    delete_orphans_pre,
    init_and_sync,
    rpm_repository_api,
    rpm_repository_version_api,
    monitor_task,
    get_content_summary,
):
    """Verify functionality with sync.

    Do the following:

    1. Create a repository, and a remote.
    2. Sync the remote.
    3. Assert that the correct number of units were added and are present in the repo.
    4. Change the "retain_package_versions" on the repository to 1 (retain the latest
       version only).
    5. Sync the remote one more time.
    6. Assert that repository version is the same as the previous one, because the older
       versions are part of modules, and they should be ignored by the retention policy.
    """

    repo, remote, task = init_and_sync(
        url=RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL,
        policy="on_demand",
        optimize=False,
        return_task=True,
    )

    # Test that, by default, everything is retained / nothing is tossed out.
    summary = get_content_summary(repo)
    assert summary["present"] == RPM_MODULAR_STATIC_FIXTURE_SUMMARY
    assert summary["added"] == RPM_MODULAR_STATIC_FIXTURE_SUMMARY
    # Test that the # of packages processed is correct
    reports = get_progress_reports_by_code(task)
    assert reports["sync.parsing.packages"].total == RPM_MODULAR_PACKAGE_COUNT
    assert reports["sync.skipped.packages"].total == 0

    # Set the retention policy to retain only 1 version of each package
    repo_data = repo.to_dict()
    repo_data.update({"retain_package_versions": 1})
    monitor_task(rpm_repository_api.update(repo.pulp_href, repo_data).task)
    repo = rpm_repository_api.read(repo.pulp_href)

    repo, remote, task = init_and_sync(
        repository=repo, remote=remote, optimize=False, return_task=True
    )

    # Test that no RPMs were removed (and no advisories etc. touched)
    # it should be the same because the older version are covered by modules
    version = rpm_repository_version_api.read(repo.latest_version_href)
    assert version.content_summary.removed == {}
    # Test that the number of packages processed is correct
    reports = get_progress_reports_by_code(task)
    assert reports["sync.parsing.packages"].total == RPM_MODULAR_PACKAGE_COUNT
    assert reports["sync.skipped.packages"].total == 0


@pytest.mark.parallel
def test_mirror_sync_with_retention_fails(init_and_sync, rpm_repository_factory):
    """Verify functionality with sync.

    Do the following:

    1. Create a repository with 'retain_package_versions' set, and a remote.
    2. Sync the remote in mirror mode.
    3. Assert that the sync fails.
    """
    repo = rpm_repository_factory(retain_package_versions=1)
    with pytest.raises(ApiException) as exc:
        init_and_sync(repository=repo, optimize=False, sync_policy="mirror_complete")

    assert exc.value.status == 400


def get_progress_reports_by_code(task):
    """Return the progress reports in a dictionary keyed by codename."""
    return {report.code: report for report in task.progress_reports}


def versions_for_packages(packages):
    """Get a list of versions for each package present in a list of Package dicts.

    Args:
        packages: List of Package info dicts
    """
    packages_by_version = defaultdict(list)

    for package in packages:
        packages_by_version[package.name].append(package.version)

    for pkg_list in packages_by_version.values():
        pkg_list.sort()

    return packages_by_version


def check_retention_policy(packages, retain_package_versions):
    """Check that the number of versions of each package <= permitted number.

    Args:
        packages: List of Package info dicts
        retention_policy: Number of package versions permitted.
    """
    return all(
        [
            len(versions) <= retain_package_versions
            for versions in versions_for_packages(packages).values()
        ]
    )
