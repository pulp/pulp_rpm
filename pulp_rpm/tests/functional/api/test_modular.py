from pulpcore.client.pulp_rpm import RpmRepositorySyncURL

from pulp_smash.pulp3.utils import gen_repo, get_content
from pulp_smash.pulp3.bindings import monitor_task

from pulp_rpm.tests.functional.constants import MODULEMD_FIELDS
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.constants import (
    RPM_SIGNED_FIXTURE_URL,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_FIXTURE_SUMMARY,
    RPM_MODULAR_FIXTURE_URL,
)


def test_is_modular_flag(
    delete_orphans_pre,
    gen_object_with_cleanup,
    rpm_package_api,
    rpm_repository_api,
    rpm_rpmremote_api,
):
    """
    Test package is marked as modular when synced from modular repository.
    """

    remote_data = gen_rpm_remote(RPM_SIGNED_FIXTURE_URL)
    remote = gen_object_with_cleanup(rpm_rpmremote_api, remote_data)
    repo_data = gen_repo(remote=remote.pulp_href)
    repo = gen_object_with_cleanup(rpm_repository_api, repo_data)
    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, sync_url)
    monitor_task(sync_response.task)

    # assert no package is marked modular
    assert rpm_package_api.list().count == RPM_FIXTURE_SUMMARY[RPM_PACKAGE_CONTENT_NAME]
    for pkg in get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
        assert pkg["is_modular"] is False

    remote_modular_data = gen_rpm_remote(RPM_MODULAR_FIXTURE_URL)
    remote_modular = gen_object_with_cleanup(rpm_rpmremote_api, remote_modular_data)
    repo_modular_data = gen_repo(remote=remote_modular.pulp_href)
    repo_modular = gen_object_with_cleanup(rpm_repository_api, repo_modular_data)
    sync_url = RpmRepositorySyncURL(remote=remote_modular.pulp_href)
    sync_response = rpm_repository_api.sync(repo_modular.pulp_href, sync_url)
    monitor_task(sync_response.task)

    # assert all package from modular repo is marked as modular
    for pkg in get_content(repo_modular.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
        assert pkg["is_modular"] is True


def test_modulemd_fields_exposed(
    delete_orphans_pre,
    gen_object_with_cleanup,
    rpm_modulemd_api,
    rpm_package_api,
    rpm_repository_api,
    rpm_rpmremote_api,
):
    """Test if profile and description info is exposed."""
    remote_data = gen_rpm_remote(RPM_MODULAR_FIXTURE_URL)
    remote = gen_object_with_cleanup(rpm_rpmremote_api, remote_data)
    repo_data = gen_repo(remote=remote.pulp_href)
    repo = gen_object_with_cleanup(rpm_repository_api, repo_data)
    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, sync_url)
    monitor_task(sync_response.task)
    modulemd_href = [md.pulp_href for md in rpm_modulemd_api.list().results if md.name == "dwm"][0]
    modulemd = rpm_modulemd_api.read(modulemd_href)
    # Check if all fields are exposed
    assert sorted(list(modulemd.to_dict().keys())) == MODULEMD_FIELDS
