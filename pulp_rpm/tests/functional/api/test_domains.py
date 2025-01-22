import json

import pytest
import uuid

from django.conf import settings

from pulpcore.client.pulp_rpm import ApiException, Copy, RpmRepositorySyncURL
from pulpcore.client.pulpcore.exceptions import ApiException as CoreApiException

from pulp_rpm.tests.functional.utils import (
    get_package_repo_path,
)
from pulp_rpm.tests.functional.constants import (
    RPM_SIGNED_FIXTURE_URL,
)

if not settings.DOMAIN_ENABLED:
    pytest.skip("Domains not enabled.", allow_module_level=True)


def test_domain_create(
    pulpcore_bindings,
    gen_object_with_cleanup,
    monitor_task,
    rpm_package_api,
    rpm_repository_api,
    rpm_rpmremote_api,
    rpm_rpmremote_factory,
):
    """Test repo-creation in a domain."""
    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)
    domain_name = domain.name

    # create and sync in default domain (not specified)
    remote = rpm_rpmremote_factory(url=RPM_SIGNED_FIXTURE_URL)
    repo_body = {"name": str(uuid.uuid4()), "remote": remote.pulp_href}
    repo = gen_object_with_cleanup(rpm_repository_api, repo_body)
    # Check that we can "find" the new repo in the default-domain
    repo = rpm_repository_api.read(repo.pulp_href)
    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    monitor_task(rpm_repository_api.sync(repo.pulp_href, sync_url).task)

    # check that newly created domain doesn't have a repo or any packages
    assert rpm_repository_api.list(pulp_domain=domain_name).count == 0
    assert rpm_package_api.list(pulp_domain=domain_name).count == 0


def test_domain_sync(
    cleanup_domains,
    pulpcore_bindings,
    gen_object_with_cleanup,
    monitor_task,
    rpm_advisory_api,
    rpm_package_api,
    rpm_package_category_api,
    rpm_package_groups_api,
    rpm_package_lang_packs_api,
    rpm_repository_api,
    rpm_rpmremote_api,
    rpm_rpmremote_factory,
):
    """Test repo-sync in a domain."""

    try:
        body = {
            "name": str(uuid.uuid4()),
            "storage_class": "pulpcore.app.models.storage.FileSystem",
            "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
        }
        domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)
        domain_name = domain.name

        # create and sync in the newly-created domain
        remote = rpm_rpmremote_factory(
            name=str(uuid.uuid4()), url=RPM_SIGNED_FIXTURE_URL, pulp_domain=domain_name
        )
        repo_body = {"name": str(uuid.uuid4()), "remote": remote.pulp_href}
        repo = gen_object_with_cleanup(rpm_repository_api, repo_body, pulp_domain=domain_name)

        # Check that we can "find" the new repo in the new domain via filtering
        repos = rpm_repository_api.list(name=repo.name, pulp_domain=domain_name).results
        assert len(repos) == 1
        assert repos[0].pulp_href == repo.pulp_href
        sync = RpmRepositorySyncURL()
        monitor_task(rpm_repository_api.sync(repo.pulp_href, sync).task)
        repo = rpm_repository_api.read(repo.pulp_href)

        # check that newly created domain has one repo (list works) and the expected contents
        assert rpm_repository_api.list(pulp_domain=domain_name).count == 1
        assert (
            rpm_package_api.list(
                repository_version=repo.latest_version_href, pulp_domain=domain_name
            ).count
            == 35
        )
        assert (
            rpm_advisory_api.list(
                repository_version=repo.latest_version_href, pulp_domain=domain_name
            ).count
            == 4
        )

        assert (
            rpm_package_category_api.list(
                repository_version=repo.latest_version_href, pulp_domain=domain_name
            ).count
            == 1
        )
        assert (
            rpm_package_groups_api.list(
                repository_version=repo.latest_version_href, pulp_domain=domain_name
            ).count
            == 2
        )
        assert (
            rpm_package_lang_packs_api.list(
                repository_version=repo.latest_version_href, pulp_domain=domain_name
            ).count
            == 1
        )
    finally:
        cleanup_domains([domain], content_api_client=rpm_package_api, cleanup_repositories=True)


@pytest.mark.parallel
def test_object_creation(
    pulpcore_bindings,
    gen_object_with_cleanup,
    rpm_repository_api,
    rpm_rpmremote_api,
    rpm_rpmremote_factory,
):
    """Test basic object creation in a separate domain."""
    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)
    domain_name = domain.name

    repo_body = {"name": str(uuid.uuid4())}
    repo = gen_object_with_cleanup(rpm_repository_api, repo_body, pulp_domain=domain_name)
    assert f"{domain_name}/api/v3/" in repo.pulp_href

    repos = rpm_repository_api.list(pulp_domain=domain_name)
    assert repos.count == 1
    assert repo.pulp_href == repos.results[0].pulp_href

    # list repos on default domain
    default_repos = rpm_repository_api.list(name=repo.name)
    assert default_repos.count == 0

    # Try to create an object w/ cross domain relations
    default_remote = rpm_rpmremote_factory()
    with pytest.raises(ApiException) as e:
        repo_body = {"name": str(uuid.uuid4()), "remote": default_remote.pulp_href}
        rpm_repository_api.create(repo_body, pulp_domain=domain.name)
    assert e.value.status == 400
    # What key should this error be under? non-field-errors seems wrong
    assert json.loads(e.value.body) == {
        "non_field_errors": [f"Objects must all be a part of the {domain_name} domain."]
    }

    with pytest.raises(ApiException) as e:
        sync_body = {"remote": default_remote.pulp_href}
        rpm_repository_api.sync(repo.pulp_href, sync_body)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": [f"Objects must all be a part of the {domain_name} domain."]
    }


@pytest.mark.parallel
def test_artifact_from_file(
    pulpcore_bindings,
    gen_object_with_cleanup,
    rpm_artifact_factory,
):
    """Test uploading artifacts in separate domains."""
    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain1 = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)

    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain2 = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)

    # Create as-artifact in domain1
    domain1_artifact = rpm_artifact_factory(pulp_domain=domain1.name)
    artifacts = pulpcore_bindings.ArtifactsApi.list(pulp_domain=domain1.name)
    assert artifacts.count == 1
    assert domain1_artifact.pulp_href == artifacts.results[0].pulp_href

    # Create as-artifact in domain2
    domain2_artifact = rpm_artifact_factory(pulp_domain=domain2.name)
    artifacts = pulpcore_bindings.ArtifactsApi.list(pulp_domain=domain2.name)
    assert artifacts.count == 1
    assert domain2_artifact.pulp_href == artifacts.results[0].pulp_href

    # Show same artifact, diff domains
    assert domain1_artifact.pulp_href != domain2_artifact.pulp_href
    assert domain1_artifact.sha256 == domain2_artifact.sha256

    # Show that duplicate artifact can not be uploaded in same domain
    with pytest.raises(CoreApiException) as e:
        rpm_artifact_factory(pulp_domain=domain1.name)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": [
            f"Artifact with sha256 checksum of '{domain1_artifact.sha256}' already exists.",
        ]
    }


@pytest.mark.parallel
def test_rpm_from_file(
    cleanup_domains,
    pulpcore_bindings,
    rpm_package_factory,
    gen_object_with_cleanup,
    rpm_package_api,
):
    """Test uploading of RPM content with domains."""
    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)

    try:
        default_content = rpm_package_factory()
        domain_content = rpm_package_factory(pulp_domain=domain.name)
        assert default_content.pulp_href != domain_content.pulp_href
        assert default_content.sha256 == domain_content.sha256

        domain_contents = rpm_package_api.list(pulp_domain=domain.name)
        assert domain_contents.count == 1
    finally:
        cleanup_domains([domain], content_api_client=rpm_package_api)


@pytest.mark.parallel
def test_content_promotion(
    cleanup_domains,
    distribution_base_url,
    pulpcore_bindings,
    download_content_unit,
    rpm_repository_api,
    rpm_rpmremote_factory,
    rpm_publication_api,
    rpm_distribution_factory,
    gen_object_with_cleanup,
    monitor_task,
):
    """Tests Content promotion path with domains: Sync->Publish->Distribute"""
    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)

    try:
        # Sync task
        remote = rpm_rpmremote_factory(pulp_domain=domain.name)
        repo_body = {"name": str(uuid.uuid4()), "remote": remote.pulp_href}
        repo = rpm_repository_api.create(repo_body, pulp_domain=domain.name)

        task = rpm_repository_api.sync(repo.pulp_href, {}).task
        response = monitor_task(task)
        assert len(response.created_resources) == 1

        repo = rpm_repository_api.read(repo.pulp_href)
        assert repo.latest_version_href[-2] == "1"

        # Publish task
        pub_body = {"repository": repo.pulp_href}
        task = rpm_publication_api.create(pub_body, pulp_domain=domain.name).task
        response = monitor_task(task)
        assert len(response.created_resources) == 1
        pub_href = response.created_resources[0]
        pub = rpm_publication_api.read(pub_href)

        assert pub.repository == repo.pulp_href

        # Distribute Task
        distro = rpm_distribution_factory(publication=pub.pulp_href, pulp_domain=domain.name)

        assert distro.publication == pub.pulp_href
        # Url structure should be host/CONTENT_ORIGIN/DOMAIN_PATH/BASE_PATH
        assert domain.name == distribution_base_url(distro.base_url).rstrip("/").split("/")[-2]

        # Check that content can be downloaded from base_url
        for pkg in ("bear-4.1-1.noarch.rpm", "pike-2.2-1.noarch.rpm"):
            pkg_path = get_package_repo_path(pkg)
            download_content_unit(distro.base_path, pkg_path, domain=domain.name)

        # Cleanup to delete the domain
        task = rpm_repository_api.delete(repo.pulp_href).task
        monitor_task(task)
    finally:
        cleanup_domains([domain], cleanup_repositories=True)


@pytest.mark.parallel
def test_domain_rbac(
    cleanup_domains, pulpcore_bindings, gen_user, gen_object_with_cleanup, rpm_repository_api
):
    """Test domain level-roles."""
    body = {
        "name": str(uuid.uuid4()),
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)

    try:
        rpm_viewer = "rpm.rpmrepository_viewer"
        rpm_creator = "rpm.rpmrepository_creator"
        user_a = gen_user(username="a", domain_roles=[(rpm_viewer, domain.pulp_href)])
        user_b = gen_user(username="b", domain_roles=[(rpm_creator, domain.pulp_href)])

        # Create two repos in different domains w/ admin user
        gen_object_with_cleanup(rpm_repository_api, {"name": str(uuid.uuid4())})
        gen_object_with_cleanup(
            rpm_repository_api, {"name": str(uuid.uuid4())}, pulp_domain=domain.name
        )

        with user_b:
            repo = gen_object_with_cleanup(
                rpm_repository_api, {"name": str(uuid.uuid4())}, pulp_domain=domain.name
            )
            repos = rpm_repository_api.list(pulp_domain=domain.name)
            assert repos.count == 1
            assert repos.results[0].pulp_href == repo.pulp_href
            # Try to create a repository in default domain
            with pytest.raises(ApiException) as e:
                rpm_repository_api.create({"name": str(uuid.uuid4())})
            assert e.value.status == 403

        with user_a:
            repos = rpm_repository_api.list(pulp_domain=domain.name)
            assert repos.count == 2
            # Try to read repos in the default domain
            repos = rpm_repository_api.list()
            assert repos.count == 0
            # Try to create a repo
            with pytest.raises(ApiException) as e:
                rpm_repository_api.create({"name": str(uuid.uuid4())}, pulp_domain=domain.name)
            assert e.value.status == 403

    finally:
        cleanup_domains([domain], cleanup_repositories=True)


@pytest.mark.parallel
def test_advisory_upload_json(
    cleanup_domains,
    setup_domain,
    upload_advisory_factory,
):
    """Test upload same advisory from JSON file into different Domains."""
    domain1 = None
    domain2 = None
    try:
        domain1, _, repo1, _ = setup_domain(sync=False)
        domain2, _, repo2, _ = setup_domain(sync=False)

        advisory1, _, an_id = upload_advisory_factory(
            pulp_domain=domain1.name, repository=repo1, set_id=True
        )
        assert advisory1.id == an_id

        advisory2, _, an_id = upload_advisory_factory(
            pulp_domain=domain2.name, repository=repo2, set_id=True
        )
        assert advisory2.id == an_id

        assert advisory1.pulp_href != advisory2.pulp_href
    finally:
        cleanup_domains([domain1, domain2], cleanup_repositories=True)


@pytest.mark.parallel
def test_cross_domain_copy_all(
    monitor_task,
    rpm_copy_api,
    cleanup_domains,
    setup_domain,
):
    """Test attempting to copy between different Domains."""
    domain1 = None
    domain2 = None
    try:
        domain1, remote1, src1, dest1 = setup_domain()
        domain2, remote2, src2, dest2 = setup_domain()
        # Success, everything in domain1
        data = Copy(
            config=[
                {"source_repo_version": src1.latest_version_href, "dest_repo": dest1.pulp_href}
            ],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data, pulp_domain=domain1.name).task)

        # Failure, call and src domain1, dest domain2
        with pytest.raises(ApiException):
            data = Copy(
                config=[
                    {"source_repo_version": src1.latest_version_href, "dest_repo": dest2.pulp_href}
                ],
                dependency_solving=False,
            )
            monitor_task(rpm_copy_api.copy_content(data, pulp_domain=domain1.name).task)

        # Failure, call domain2, src/dest domain1
        with pytest.raises(ApiException):
            data = Copy(
                config=[
                    {"source_repo_version": src1.latest_version_href, "dest_repo": dest1.pulp_href}
                ],
                dependency_solving=False,
            )
            monitor_task(rpm_copy_api.copy_content(data, pulp_domain=domain2.name).task)

    finally:
        cleanup_domains([domain1, domain2], cleanup_repositories=True)


@pytest.mark.parallel
def test_cross_domain_content(
    cleanup_domains,
    monitor_task,
    rpm_advisory_api,
    rpm_copy_api,
    rpm_repository_api,
    setup_domain,
):
    """Test the content parameter."""
    domain1 = None
    domain2 = None
    try:
        domain1, remote1, src1, dest1 = setup_domain()
        domain2, remote2, src2, dest2 = setup_domain()

        # Copy content1 from src1 to dest1, expect 2 copied advisories
        advisories1 = rpm_advisory_api.list(
            repository_version=src1.latest_version_href, pulp_domain=domain1.name
        ).results
        advisories_to_copy1 = (advisories1[0].pulp_href, advisories1[1].pulp_href)

        data = Copy(
            config=[
                {
                    "source_repo_version": src1.latest_version_href,
                    "dest_repo": dest1.pulp_href,
                    "content": advisories_to_copy1,
                }
            ],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data, pulp_domain=domain1.name).task)
        dest1 = rpm_repository_api.read(dest1.pulp_href)
        advisories = rpm_advisory_api.list(
            repository_version=dest1.latest_version_href, pulp_domain=domain1.name
        ).results
        assert 2 == len(advisories)

        # Copy content1 from src1 to dest1, domain2, expect failure
        with pytest.raises(ApiException):
            data = Copy(
                config=[
                    {
                        "source_repo_version": src1.latest_version_href,
                        "dest_repo": dest2.pulp_href,
                        "content": advisories_to_copy1,
                    }
                ],
                dependency_solving=False,
            )
            monitor_task(rpm_copy_api.copy_content(data, pulp_domain=domain1.name).task)

        # Copy content1 from src1 to dest2, domain1, expect failure
        with pytest.raises(ApiException):
            data = Copy(
                config=[
                    {
                        "source_repo_version": src1.latest_version_href,
                        "dest_repo": dest2.pulp_href,
                        "content": advisories_to_copy1,
                    }
                ],
                dependency_solving=False,
            )
            monitor_task(rpm_copy_api.copy_content(data, pulp_domain=domain1.name).task)

        # Copy mixed content from src2 to dest2, domain2, expect failure
        advisories2 = rpm_advisory_api.list(
            repository_version=src2.latest_version_href, pulp_domain=domain2.name
        ).results
        advisories_to_copy2 = (advisories2[0].pulp_href, advisories2[1].pulp_href)

        with pytest.raises(ApiException):
            data = Copy(
                config=[
                    {
                        "source_repo_version": src2.latest_version_href,
                        "dest_repo": dest2.pulp_href,
                        "content": advisories_to_copy1 + advisories_to_copy2,
                    }
                ],
                dependency_solving=False,
            )
            task = rpm_copy_api.copy_content(data, pulp_domain=domain2.name).task
            monitor_task(task)

    finally:
        cleanup_domains([domain1, domain2], cleanup_repositories=True)
