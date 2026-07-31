"""Test copy with a repository large enough to exceed PostgreSQL's 65535 parameter limit."""

import uuid

import pytest

from pulpcore.client.pulp_rpm import Copy, RpmRepositorySyncURL, RpmRpmRemote, RpmRpmRepository

from pulp_rpm.tests.functional.utils import MetaPackage, RepositoryBuilder

CONTENT_COUNT = 70_000


@pytest.fixture(scope="module")
def large_rpm_repo(rpm_repository_api, rpm_rpmremote_api, monitor_task, tmp_path_factory):
    """Sync a 70k-package repo from synthetic metadata. Reused across the module."""
    tmp_path = tmp_path_factory.mktemp("large_repo")
    builder = RepositoryBuilder(tmp_path)

    packages = [
        MetaPackage(
            nevra=MetaPackage.generate_nevra(i),
            digest=MetaPackage.generate_digest(i),
            time_build=1,
            location=f"pkg{i}.rpm",
        )
        for i in range(CONTENT_COUNT)
    ]
    remote_repo = builder.build(packages)

    repo = rpm_repository_api.create(RpmRpmRepository(name=str(uuid.uuid4())))
    remote = rpm_rpmremote_api.create(
        RpmRpmRemote(name=str(uuid.uuid4()), url=remote_repo.url, policy="on_demand")
    )
    sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
    monitor_task(rpm_repository_api.sync(repo.pulp_href, sync_data).task)
    repo = rpm_repository_api.read(repo.pulp_href)

    yield repo

    rpm_repository_api.delete(repo.pulp_href)
    rpm_rpmremote_api.delete(remote.pulp_href)


@pytest.mark.skip(reason="Takes too long for CI; use for manual reproduction only")
@pytest.mark.parallel
def test_copy_large_repo(
    large_rpm_repo,
    monitor_task,
    rpm_copy_api,
    rpm_repository_api,
    rpm_repository_factory,
    get_content_summary,
):
    """Copy all content from a 70k-package repo to an empty repo.

    Reproduces the '65535 parameter limit' failure that occurs when
    RepositoryVersion.content materializes content_ids as SQL parameters
    and the copy task unions/filters those querysets.
    """
    dest = rpm_repository_factory()
    data = Copy(
        config=[
            {
                "source_repo_version": large_rpm_repo.latest_version_href,
                "dest_repo": dest.pulp_href,
            }
        ],
        dependency_solving=False,
    )
    monitor_task(rpm_copy_api.copy_content(data).task)

    dest = rpm_repository_api.read(dest.pulp_href)
    summary = get_content_summary(dest)
    assert summary["present"]["rpm.package"]["count"] == CONTENT_COUNT
