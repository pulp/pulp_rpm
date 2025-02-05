import pytest

from pulpcore.client.pulp_rpm import PrunePackages
from pulpcore.client.pulp_rpm.exceptions import ApiException


def test_01_prune_params(init_and_sync, rpm_prune_api, monitor_task_group):
    """Assert on various param-validation errors."""
    # create/sync rpm repo
    repo, _ = init_and_sync(policy="on_demand")

    params = PrunePackages(repo_hrefs=[])
    # requires repo-href or *
    with pytest.raises(ApiException) as exc:
        rpm_prune_api.prune_packages(params)
    assert "Must not be []" in exc.value.body

    params.repo_hrefs = ["foo"]
    with pytest.raises(ApiException) as exc:
        rpm_prune_api.prune_packages(params)
    assert "URI not valid" in exc.value.body

    params.repo_hrefs = ["*", repo.pulp_href]
    with pytest.raises(ApiException) as exc:
        rpm_prune_api.prune_packages(params)
    assert "Can't specify specific HREFs when using" in exc.value.body

    # '*' only'
    params.repo_hrefs = ["*"]
    params.dry_run = True
    params.keep_days = 1000
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 0 == task_group.failed

    # Valid repo-href
    params.repo_hrefs = [repo.pulp_href]
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == task_group.completed
    assert 0 == task_group.failed

    # Valid +int
    params.keep_days = 1000
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == task_group.completed
    assert 0 == task_group.failed

    # Valid 0
    params.keep_days = 0
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == task_group.completed
    assert 0 == task_group.failed

    # Valid dry-run
    params.dry_run = True
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == task_group.completed
    assert 0 == task_group.failed


def test_02_prune_dry_run(init_and_sync, rpm_prune_api, monitor_task_group, monitor_task):
    # create/sync rpm repo
    repo, _ = init_and_sync(policy="on_demand")

    # prune keep=0 dry_run=True -> expect total=4 done=0
    params = PrunePackages(repo_hrefs=[repo.pulp_href], keep_days=0, dry_run=True)
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == len(task_group.tasks)
    assert 2 == task_group.completed
    assert 0 == task_group.failed
    assert 1 == len(task_group.group_progress_reports)

    prog_rpt = task_group.group_progress_reports[0]
    assert 1 == prog_rpt.done
    assert 1 == prog_rpt.total
    for t in task_group.tasks:
        if t.name == "pulp_rpm.app.tasks.prune.prune_repo_packages":
            prune_task = monitor_task(t.pulp_href)
            assert 1 == len(prune_task.progress_reports)
            assert 4 == prune_task.progress_reports[0].total
            assert 0 == prune_task.progress_reports[0].done

    # prune keep=1000 dry_run=True -> expect total=0 done=0
    params = PrunePackages(repo_hrefs=[repo.pulp_href], keep_days=1000, dry_run=True)
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == len(task_group.tasks)
    assert 2 == task_group.completed
    assert 0 == task_group.failed
    for t in task_group.tasks:
        if t.name == "pulp_rpm.app.tasks.prune.prune_repo_packages":
            prune_task = monitor_task(t.pulp_href)
            assert 1 == len(prune_task.progress_reports)
            assert 0 == prune_task.progress_reports[0].total
            assert 0 == prune_task.progress_reports[0].done


def test_03_prune_results(
    init_and_sync,
    rpm_prune_api,
    monitor_task_group,
    monitor_task,
    rpm_repository_api,
    rpm_repository_version_api,
):
    # create/sync rpm repo
    repo, _ = init_and_sync(policy="on_demand")

    # prune keep=0 dry_run=False -> expect total=4 done=4
    params = PrunePackages(repo_hrefs=[repo.pulp_href], keep_days=0, dry_run=False)
    task_group = monitor_task_group(rpm_prune_api.prune_packages(params).task_group)
    assert 2 == len(task_group.tasks)
    assert 2 == task_group.completed
    assert 0 == task_group.failed

    for t in task_group.tasks:
        if t.name == "pulp_rpm.app.tasks.prune.prune_repo_packages":
            prune_task = monitor_task(t.pulp_href)
            assert 1 == len(prune_task.progress_reports)
            assert 4 == prune_task.progress_reports[0].total
            assert 4 == prune_task.progress_reports[0].done

    # investigate content -> 4 fewer packages, correct dups gone
    repo2 = rpm_repository_api.read(repo.pulp_href)
    rv = rpm_repository_version_api.read(repo2.latest_version_href)
    assert 4 == rv.content_summary.removed["rpm.package"]["count"]
