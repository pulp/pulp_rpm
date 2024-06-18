"""Tests distribution trees."""

import pytest

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_DISTRIBUTION_TREE,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_DISTRIBUTION_TREE_CHANGED_ADDON_URL,
    RPM_DISTRIBUTION_TREE_CHANGED_MAIN_URL,
    RPM_DISTRIBUTION_TREE_CHANGED_VARIANT_URL,
)


@pytest.mark.parallel
def test_simple_copy_distribution_tree(
    rpm_kickstart_repo_immediate,
    rpm_repository_factory,
    rpm_repository_version_api,
    rpm_copy_api,
    monitor_task,
):
    """Sync repository with a distribution tree."""
    dest_repo = rpm_repository_factory()
    config = [
        {
            "source_repo_version": rpm_kickstart_repo_immediate.latest_version_href,
            "dest_repo": dest_repo.pulp_href,
        }
    ]

    response = rpm_copy_api.copy_content({"config": config, "dependency_solving": True})
    task = monitor_task(response.task)
    assert len(task.created_resources) == 1
    assert task.created_resources[0] == f"{dest_repo.versions_href}1/"

    dest_repo_ver = rpm_repository_version_api.read(task.created_resources[0])
    assert dest_repo_ver.content_summary.added[PULP_TYPE_DISTRIBUTION_TREE]["count"] == 1


@pytest.mark.parallel
def test_dist_tree_copy_as_content(
    rpm_kickstart_repo_immediate,
    rpm_repository_factory,
    rpm_content_distribution_trees_api,
    rpm_copy_api,
    monitor_task,
):
    """Test sync distribution tree repository and copy it."""
    assert rpm_kickstart_repo_immediate.latest_version_href.endswith("/1/")
    source_content = rpm_content_distribution_trees_api.list(
        repository_version=rpm_kickstart_repo_immediate.latest_version_href
    )
    distribution_tree_href = source_content.results[0].pulp_href
    repo_copy = rpm_repository_factory()

    copy_config = [
        {
            "source_repo_version": rpm_kickstart_repo_immediate.latest_version_href,
            "dest_repo": repo_copy.pulp_href,
            "content": [distribution_tree_href],
        }
    ]
    response = rpm_copy_api.copy_content({"config": copy_config, "dependency_solving": True})
    task = monitor_task(response.task)
    assert len(task.created_resources) == 1
    dest_repo_ver = task.created_resources[0]
    assert dest_repo_ver == f"{repo_copy.versions_href}1/"

    dest_content = rpm_content_distribution_trees_api.list(repository_version=dest_repo_ver)
    assert source_content.count == dest_content.count == 1
    assert {p.pulp_href for p in source_content.results} == {
        p.pulp_href for p in dest_content.results
    }


@pytest.mark.parallel
def test_skip_treeinfo(init_and_sync, has_pulp_plugin):
    # Sync repo. Should create only main repo, not subrepos
    _, _, task = init_and_sync(
        url=RPM_KICKSTART_FIXTURE_URL, skip_types=["treeinfo"], return_task=True
    )
    rsrvd = "prn:rpm.rpmrepository" if has_pulp_plugin("core", "3.55") else "/repositories/rpm/rpm/"
    rsrvd_repos = [r for r in task.reserved_resources_record if rsrvd in r]
    assert 1 == len(rsrvd_repos)

    # Sync again, including kstree. Should end up w/ 5 repos reserved.
    _, _, task = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL, return_task=True)
    rsrvd_repos = [r for r in task.reserved_resources_record if rsrvd in r]
    assert 5 == len(rsrvd_repos)


def test_sync_dist_tree_change_addon_repo(init_and_sync, rpm_package_api, delete_orphans_pre):
    """Test changed addon repository."""
    addon_test_pkg_name = "test-srpm02"
    repo, remote = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL)

    # check testing package is not present
    packages = rpm_package_api.list().results
    assert addon_test_pkg_name not in [p.name for p in packages]

    # re-sync w/ new remote & update repo object
    init_and_sync(repository=repo, url=RPM_DISTRIBUTION_TREE_CHANGED_ADDON_URL)

    # check new pacakge is synced to subrepo
    packages = rpm_package_api.list().results
    assert addon_test_pkg_name in [p.name for p in packages]


def test_sync_dist_tree_change_main_repo(init_and_sync, rpm_package_api, delete_orphans_pre):
    """Test changed main repository."""
    main_repo_test_pkg_name = "test-srpm01"
    repo, remote = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL)
    repo_version_num = repo.latest_version_href.rstrip("/")[-1]

    # re-sync w/ new remote & update repo object
    repo, remote = init_and_sync(repository=repo, url=RPM_DISTRIBUTION_TREE_CHANGED_MAIN_URL)
    updated_repo_version_num = repo.latest_version_href.rstrip("/")[-1]

    # Assert new content was added and repo version was increased
    assert repo_version_num < updated_repo_version_num
    packages = rpm_package_api.list().results
    assert main_repo_test_pkg_name in [p.name for p in packages]


def test_sync_dist_tree_change_variant_repo(init_and_sync, rpm_package_api, delete_orphans_pre):
    """Test changed variant repository."""
    variant_test_pkg_name = "test-srpm03"
    repo, remote = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL)

    # check testing package is not present
    packages = rpm_package_api.list().results
    assert variant_test_pkg_name not in [p.name for p in packages]

    # re-sync w/ new remote & update repo object
    init_and_sync(repository=repo, url=RPM_DISTRIBUTION_TREE_CHANGED_VARIANT_URL)

    # check new pacakge is synced to subrepo
    packages = rpm_package_api.list().results
    assert variant_test_pkg_name in [p.name for p in packages]


def test_remove_repo_with_distribution_tree(
    init_and_sync,
    rpm_repository_api,
    rpm_content_distribution_trees_api,
    pulpcore_bindings,
    monitor_task,
):
    """Sync repository with distribution tree and remove the repository."""
    response = pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0})
    monitor_task(response.task)

    num_repos_start = rpm_repository_api.list().count
    num_disttrees_start = rpm_content_distribution_trees_api.list().count

    repo, _ = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL)
    task = rpm_repository_api.delete(repo.pulp_href)
    monitor_task(task.task)

    assert rpm_repository_api.list().count == num_repos_start
    # Remove orphans and check if distribution tree was removed.
    response = pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0})
    monitor_task(response.task)
    assert rpm_content_distribution_trees_api.list().count == num_disttrees_start
