import json
import subprocess

from pulp_rpm.tests.functional.constants import (
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_SIZE,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_KICKSTART_FIXTURE_SIZE,
)


def test_repo_size(init_and_sync, delete_orphans_pre, monitor_task, pulpcore_bindings):
    """Test that RPM repos correctly report their on-disk artifact sizes."""
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)
    repo, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")

    cmd = (
        "pulpcore-manager",
        "repository-size",
        "--repositories",
        repo.pulp_href,
        "--include-on-demand",
    )
    run = subprocess.run(cmd, capture_output=True, check=True)
    out = json.loads(run.stdout)

    # Assert basic items of report and test on-demand sizing
    assert len(out) == 1
    report = out[0]
    assert report["name"] == repo.name
    assert report["href"] == repo.pulp_href
    assert report["disk-size"] == 0
    assert report["on-demand-size"] == RPM_UNSIGNED_FIXTURE_SIZE

    _, _ = init_and_sync(repository=repo, url=RPM_UNSIGNED_FIXTURE_URL, policy="immediate")
    run = subprocess.run(cmd, capture_output=True, check=True)
    report = json.loads(run.stdout)[0]
    assert report["disk-size"] == RPM_UNSIGNED_FIXTURE_SIZE
    assert report["on-demand-size"] == 0


def test_kickstart_repo_size(init_and_sync, delete_orphans_pre, monitor_task, pulpcore_bindings):
    """Test that kickstart RPM repos correctly report their on-disk artifact sizes."""
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)
    repo, _ = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL, policy="on_demand")

    cmd = (
        "pulpcore-manager",
        "repository-size",
        "--repositories",
        repo.pulp_href,
        "--include-on-demand",
    )
    run = subprocess.run(cmd, capture_output=True, check=True)
    out = json.loads(run.stdout)

    # Assert basic items of report and test on-demand sizing
    assert len(out) == 1
    report = out[0]
    assert report["name"] == repo.name
    assert report["href"] == repo.pulp_href
    assert report["disk-size"] == 2275  # One file is always downloaded
    assert report["on-demand-size"] == 133810  # Not all remote artifacts have sizes

    _, _ = init_and_sync(repository=repo, url=RPM_KICKSTART_FIXTURE_URL, policy="immediate")
    run = subprocess.run(cmd, capture_output=True, check=True)
    report = json.loads(run.stdout)[0]
    assert report["disk-size"] == RPM_KICKSTART_FIXTURE_SIZE
    assert report["on-demand-size"] == 0
