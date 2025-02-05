import pytest
import uuid

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL
from pulpcore.client.pulp_rpm.exceptions import ApiException

from pulp_rpm.tests.functional.constants import (
    RPM_SIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_FIXTURE_SUMMARY,
)


@pytest.mark.parallel
def test_rbac_repositories(gen_user, rpm_repository_factory, rpm_repository_api, monitor_task):
    """
    Test creation of repository with user with permissions and without.
    """
    user_creator = gen_user(model_roles=["rpm.rpmrepository_creator", "rpm.rpmremote_creator"])
    user_viewer = gen_user(model_roles=["rpm.viewer"])
    user_no = gen_user()

    repo = None

    # Create repository
    with user_creator:
        repo = rpm_repository_factory()
        assert rpm_repository_api.read(repo.pulp_href)

    with user_viewer, pytest.raises(ApiException):
        rpm_repository_factory()

    with user_no, pytest.raises(ApiException):
        rpm_repository_factory()

    # List & retrieve repository
    with user_creator:
        assert rpm_repository_api.list(name=repo.name).count == 1
        assert repo.pulp_href == rpm_repository_api.read(repo.pulp_href).pulp_href

    with user_viewer:
        assert rpm_repository_api.list(name=repo.name).count == 1
        assert repo.pulp_href == rpm_repository_api.read(repo.pulp_href).pulp_href

    with user_no, pytest.raises(ApiException) as exc:
        assert rpm_repository_api.list(name=repo.name).count == 0
        rpm_repository_api.read(repo.pulp_href)
    assert exc.value.status == 404

    # Update repository
    with user_creator:
        repo_data = repo.to_dict()
        repo_data.update(name="rpm_repo_test_modify")
        monitor_task(rpm_repository_api.update(repo.pulp_href, repo_data).task)
        assert rpm_repository_api.read(repo.pulp_href).name == "rpm_repo_test_modify"

    with user_no, pytest.raises(ApiException) as exc:
        repo_data = repo.to_dict()
        repo_data.update(name="rpm_repo_test_modify_without_perms")
        rpm_repository_api.update(repo.pulp_href, repo_data)
    # Here is response `404` as user doesn't have even permission to retrieve repo data
    # so pulp response with not found instead `access denied` to not expose it exists
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        repo_data = repo.to_dict()
        repo_data.update(name="rpm_repo_test_modify_with_view_perms")
        rpm_repository_api.update(repo.pulp_href, repo_data)
    # Fails with '403' as a repo can be seen but not updated.
    assert exc.value.status == 403

    # Remove repository
    # Fails with `404` not found for same reason as `update` above
    with user_no, pytest.raises(ApiException) as exc:
        rpm_repository_api.delete(repo.pulp_href)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_repository_api.delete(repo.pulp_href)
    assert exc.value.status == 403

    with user_creator:
        response = rpm_repository_api.delete(repo.pulp_href)
        monitor_task(response.task)
        assert rpm_repository_api.list(name=repo.name).count == 0


@pytest.mark.parallel
def test_rbac_remotes_and_sync(
    gen_user,
    rpm_rpmremote_api,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_rpmremote_factory,
    monitor_task,
):
    """
    Test creation of remotes with user with permissions and without.

    Then to test sync of one of those remote.
    """
    user_creator = gen_user(
        model_roles=[
            "rpm.rpmremote_creator",
            "rpm.rpmrepository_creator",
        ]
    )
    user_viewer = gen_user(model_roles=["rpm.viewer"])
    user_no = gen_user(model_roles=["rpm.rpmrepository_creator"])

    remote = None

    # Create
    with user_no, pytest.raises(ApiException) as exc:
        rpm_rpmremote_factory(url=RPM_SIGNED_FIXTURE_URL)
    assert exc.value.status == 403

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_rpmremote_factory(url=RPM_SIGNED_FIXTURE_URL)
    assert exc.value.status == 403

    with user_creator:
        remote = rpm_rpmremote_factory(url=RPM_SIGNED_FIXTURE_URL)
        assert rpm_rpmremote_api.list(name=remote.name).count == 1

    # Update
    remote_data_update = remote.to_dict()
    remote_data_update["url"] = RPM_UNSIGNED_FIXTURE_URL

    with user_no, pytest.raises(ApiException) as exc:
        rpm_rpmremote_api.update(remote.pulp_href, remote_data_update)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_rpmremote_api.update(remote.pulp_href, remote_data_update)
    # 403 as user can view content but not update
    assert exc.value.status == 403

    with user_creator:
        res = rpm_rpmremote_api.update(remote.pulp_href, remote_data_update)
        monitor_task(res.task)
        remote = rpm_rpmremote_api.read(remote.pulp_href)
        remotes = rpm_rpmremote_api.list(name=remote_data_update["name"]).results
        assert len(remotes) == 1
        assert remotes[0].url == RPM_UNSIGNED_FIXTURE_URL

    # Sync the remote
    with user_no, pytest.raises(ApiException) as exc:
        repo = rpm_repository_factory(remote=remote.pulp_href)
        sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
        rpm_repository_api.sync(repo.pulp_href, sync_url)
    assert exc.value.status == 403

    with user_viewer, pytest.raises(ApiException) as exc:
        repo = rpm_repository_factory(remote=remote.pulp_href)
        sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
        rpm_repository_api.sync(repo.pulp_href, sync_url)
    assert exc.value.status == 403

    with user_creator:
        repo = rpm_repository_factory(remote=remote.pulp_href)
        sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_res = rpm_repository_api.sync(repo.pulp_href, sync_url)
        monitor_task(sync_res.task)
        repo = rpm_repository_api.read(repo.pulp_href)
        assert repo.latest_version_href.endswith("/1/")

    # Remove
    with user_no, pytest.raises(ApiException) as exc:
        rpm_repository_api.delete(remote.pulp_href)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_repository_api.delete(remote.pulp_href)
    assert exc.value.status == 403

    with user_creator:
        response = rpm_rpmremote_api.delete(remote.pulp_href)
        monitor_task(response.task)
        response = rpm_repository_api.delete(repo.pulp_href)
        monitor_task(response.task)
        assert rpm_rpmremote_api.list(name=remote.name).count == 0
        assert rpm_repository_api.list(name=repo.name).count == 0


@pytest.mark.parallel
def test_rbac_acs(gen_user, rpm_acs_api, rpm_rpmremote_api, rpm_rpmremote_factory, monitor_task):
    """Test RPM ACS CRUD."""
    user_creator = gen_user(
        model_roles=[
            "rpm.rpmalternatecontentsource_creator",
            "rpm.rpmremote_owner",
        ]
    )
    user_viewer = gen_user(
        model_roles=[
            "rpm.viewer",
            "rpm.rpmremote_owner",
        ]
    )
    user_no = gen_user(
        model_roles=[
            "rpm.rpmremote_owner",
        ]
    )

    acs = None
    remote = rpm_rpmremote_factory(policy="on_demand")

    acs_data = {
        "name": str(uuid.uuid4()),
        "remote": remote.pulp_href,
    }

    # Create
    with user_no, pytest.raises(ApiException) as exc:
        rpm_acs_api.create(acs_data)
    assert exc.value.status == 403

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_acs_api.create(acs_data)
    assert exc.value.status == 403

    with user_creator:
        acs = rpm_acs_api.create(acs_data)
        assert rpm_acs_api.list(name=acs.name).count == 1

    # Update & Read
    with user_no, pytest.raises(ApiException) as exc:
        rpm_acs_api.read(acs.pulp_href)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        acs_to_update = rpm_acs_api.read(acs.pulp_href).to_dict()
        acs_to_update["paths"][0] = "files/"
        rpm_acs_api.update(acs.pulp_href, acs_to_update)
    assert exc.value.status == 403

    with user_creator:
        acs_to_update = rpm_acs_api.read(acs.pulp_href).to_dict()
        acs_to_update["paths"][0] = "files/"
        response = rpm_acs_api.update(acs.pulp_href, acs_to_update)
        monitor_task(response.task)
        assert rpm_acs_api.list(name=acs.name).count == 1
        assert "files/" in rpm_acs_api.read(acs.pulp_href).paths

    # Remove
    with user_no, pytest.raises(ApiException) as exc:
        rpm_acs_api.delete(acs.pulp_href)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_acs_api.delete(acs.pulp_href)
    assert exc.value.status == 403

    with user_creator:
        response = rpm_acs_api.delete(acs.pulp_href)
        monitor_task(response.task)
        response = rpm_rpmremote_api.delete(remote.pulp_href)
        monitor_task(response.task)
        assert rpm_acs_api.list(name=acs.name).count == 0


@pytest.mark.parallel
def test_rbac_publication(
    gen_user,
    rpm_rpmremote_api,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_publication_factory,
    rpm_publication_api,
    monitor_task,
):
    """Test RPM publication CRUD."""
    user_creator = gen_user(
        model_roles=[
            "rpm.rpmpublication_creator",
            "rpm.rpmremote_creator",
            "rpm.rpmrepository_creator",
        ]
    )
    user_viewer = gen_user(
        model_roles=[
            "rpm.viewer",
        ]
    )
    user_no = gen_user(model_roles=[])

    # Create
    with user_creator:
        repo = rpm_repository_factory()
        publication = rpm_publication_factory(repository=repo.pulp_href)
        assert publication.repository == repo.pulp_href
        pub_from_repo_version = rpm_publication_factory(repository_version=repo.latest_version_href)
        assert pub_from_repo_version.repository_version == repo.latest_version_href
    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_publication_factory(repository=repo.pulp_href)
    assert exc.value.status == 403

    with user_no, pytest.raises(ApiException) as exc:
        rpm_publication_factory(repository=repo.pulp_href)
    assert exc.value.status == 403

    # Remove
    with user_no, pytest.raises(ApiException) as exc:
        rpm_publication_api.delete(publication.pulp_href)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_publication_api.delete(publication.pulp_href)
    assert exc.value.status == 403

    with user_creator:
        rpm_publication_api.delete(publication.pulp_href)
        res = rpm_repository_api.delete(repo.pulp_href)
        monitor_task(res.task)
        publications = rpm_publication_api.list().results
        assert not any(p.repository != repo.pulp_href for p in publications)


@pytest.mark.parallel
def test_rbac_distribution(
    gen_user,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_rpmremote_api,
    rpm_publication_api,
    rpm_publication_factory,
    rpm_distribution_api,
    rpm_distribution_factory,
    monitor_task,
):
    """Test RPM distribution CRUD."""
    user_creator = gen_user(
        model_roles=[
            "rpm.rpmrepository_creator",
            "rpm.rpmpublication_creator",
            "rpm.rpmdistribution_creator",
        ]
    )
    user_viewer = gen_user(
        model_roles=[
            "rpm.viewer",
        ]
    )
    user_no = gen_user(model_roles=[])

    # Create
    with user_no, pytest.raises(ApiException) as exc:
        rpm_distribution_factory(name=str(uuid.uuid4()), base_path=str(uuid.uuid4()))
    assert exc.value.status == 403

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_distribution_factory(name=str(uuid.uuid4()), base_path=str(uuid.uuid4()))
    assert exc.value.status == 403

    with user_creator:
        repo = rpm_repository_factory()
        publication = rpm_publication_factory(repository=repo.pulp_href)
        distribution = rpm_distribution_factory(publication=publication.pulp_href)
        assert distribution.publication == publication.pulp_href

    # Update
    dist_data_to_update = rpm_distribution_api.read(distribution.pulp_href).to_dict()
    new_name = str(uuid.uuid4())
    dist_data_to_update["name"] = new_name

    with user_no, pytest.raises(ApiException) as exc:
        rpm_distribution_api.update(distribution.pulp_href, dist_data_to_update)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_distribution_api.update(distribution.pulp_href, dist_data_to_update)
    assert exc.value.status == 403

    with user_creator:
        res = rpm_distribution_api.update(distribution.pulp_href, dist_data_to_update)
        monitor_task(res.task)
        assert rpm_distribution_api.list(name=new_name).count == 1

    # Remove
    with user_no, pytest.raises(ApiException) as exc:
        rpm_distribution_api.delete(distribution.pulp_href)
    assert exc.value.status == 404

    with user_viewer, pytest.raises(ApiException) as exc:
        rpm_distribution_api.delete(distribution.pulp_href)
    assert exc.value.status == 403

    with user_creator:
        rpm_distribution_api.delete(distribution.pulp_href)
        rpm_publication_api.delete(publication.pulp_href)

        res = rpm_repository_api.delete(repo.pulp_href)
        monitor_task(res.task)

        assert rpm_distribution_api.list(name=distribution.name).count == 0
        assert rpm_repository_api.list(name=repo.name).count == 0


@pytest.mark.parallel
def test_rbac_content_scoping(
    gen_user,
    rpm_advisory_api,
    rpm_package_api,
    rpm_package_category_api,
    rpm_package_groups_api,
    rpm_package_lang_packs_api,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_rpmremote_api,
    rpm_rpmremote_factory,
    monitor_task,
):
    """
    Test creation of remotes with user with permissions and without.

    Then to test sync of one of those remote.
    """
    user_creator = gen_user(
        model_roles=[
            "rpm.rpmremote_creator",
            "rpm.rpmrepository_creator",
        ]
    )
    user_viewer = gen_user(model_roles=["rpm.viewer"])
    user_no = gen_user(model_roles=["rpm.rpmrepository_creator"])

    remote = None

    # Create
    with user_creator:
        remote = rpm_rpmremote_factory(url=RPM_SIGNED_FIXTURE_URL)
        assert rpm_rpmremote_api.list().count == 1

    # Sync the remote
    with user_creator:
        repo = rpm_repository_factory(remote=remote.pulp_href)
        sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_res = rpm_repository_api.sync(repo.pulp_href, sync_url)
        monitor_task(sync_res.task)
        repo = rpm_repository_api.read(repo.pulp_href)
        assert repo.latest_version_href.endswith("/1/")

    def _assert_listed_content():
        packages_count = rpm_package_api.list(repository_version=repo.latest_version_href).count
        assert RPM_FIXTURE_SUMMARY["rpm.package"]["count"] == packages_count

        advisories_count = rpm_advisory_api.list(repository_version=repo.latest_version_href).count
        assert RPM_FIXTURE_SUMMARY["rpm.advisory"]["count"] == advisories_count

        package_categories_count = rpm_package_category_api.list(
            repository_version=repo.latest_version_href
        ).count
        assert RPM_FIXTURE_SUMMARY["rpm.packagecategory"]["count"] == package_categories_count

        package_groups_count = rpm_package_groups_api.list(
            repository_version=repo.latest_version_href
        ).count
        assert RPM_FIXTURE_SUMMARY["rpm.packagegroup"]["count"] == package_groups_count

        package_lang_packs_count = rpm_package_lang_packs_api.list(
            repository_version=repo.latest_version_href
        ).count
        assert RPM_FIXTURE_SUMMARY["rpm.packagelangpacks"]["count"] == package_lang_packs_count

    # Test content visibility
    # TODO: modules
    with user_creator:
        _assert_listed_content()

    with user_viewer:
        _assert_listed_content()

    with user_no:
        assert 0 == rpm_package_api.list(repository_version=repo.latest_version_href).count
        assert 0 == rpm_advisory_api.list(repository_version=repo.latest_version_href).count
        assert 0 == rpm_package_category_api.list(repository_version=repo.latest_version_href).count
        assert 0 == rpm_package_groups_api.list(repository_version=repo.latest_version_href).count
        assert (
            0 == rpm_package_lang_packs_api.list(repository_version=repo.latest_version_href).count
        )

    # Remove
    with user_creator:
        response = rpm_rpmremote_api.delete(remote.pulp_href)
        monitor_task(response.task)
        response = rpm_repository_api.delete(repo.pulp_href)
        monitor_task(response.task)
        assert rpm_rpmremote_api.list(name=remote.name).count == 0
        assert rpm_repository_api.list(name=repo.name).count == 0
