import pytest

from pulpcore.tests.functional.utils import PulpTaskError

from pulp_rpm.tests.functional.constants import (
    PULP_FIXTURES_BASE_URL,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_KICKSTART_ONLY_META_FIXTURE_URL,
    RPM_ONLY_METADATA_REPO_URL,
)

from pulpcore.client.pulp_rpm import (
    RpmRepositorySyncURL,
)


@pytest.mark.parametrize(
    "paths,remote_url,content_summary",
    [
        (["rpm-unsigned/"], RPM_ONLY_METADATA_REPO_URL, RPM_FIXTURE_SUMMARY),
        (
            ["rpm-distribution-tree/"],
            RPM_KICKSTART_ONLY_META_FIXTURE_URL,
            RPM_KICKSTART_FIXTURE_SUMMARY,
        ),
    ],
)
def test_acs_simple(
    paths,
    remote_url,
    content_summary,
    rpm_repository_version_api,
    rpm_repository_api,
    rpm_acs_api,
    rpm_repository_factory,
    rpm_rpmremote_factory,
    get_content_summary,
    monitor_task,
    monitor_task_group,
    gen_object_with_cleanup,
    delete_orphans_pre,
):
    """Test to sync repo with use of ACS."""
    # ACS is rpm-unsigned repository which has all packages needed
    acs_remote = rpm_rpmremote_factory(url=PULP_FIXTURES_BASE_URL, policy="on_demand")

    acs_data = {
        "name": "alternatecontentsource",
        "remote": acs_remote.pulp_href,
        "paths": paths,
    }
    acs = gen_object_with_cleanup(rpm_acs_api, acs_data)

    repo = rpm_repository_factory()
    remote = rpm_rpmremote_factory(url=remote_url)

    # Sync repo with metadata only, before ACS refresh it should fail
    repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)

    with pytest.raises(PulpTaskError) as ctx:
        sync_response = rpm_repository_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

    assert "404, message='Not Found'" in ctx.value.task.error["description"]

    # ACS refresh
    acs_refresh = rpm_acs_api.refresh(acs.pulp_href)
    monitor_task_group(acs_refresh.task_group)

    # Sync repository with metadata only
    sync_response = rpm_repository_api.sync(repo.pulp_href, repository_sync_data)
    monitor_task(sync_response.task)

    repo = rpm_repository_api.read(repo.pulp_href)
    present_summary = get_content_summary(repo)["present"]
    assert present_summary == content_summary
