import uuid

import pytest

from pulpcore.client.pulp_rpm import (
    ApiClient as RpmApiClient,
    ContentRepoMetadataFilesApi,
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RepositoriesRpmVersionsApi,
    RpmRepositorySyncURL,
)

from pulp_rpm.tests.functional.constants import (
    RPM_UNSIGNED_FIXTURE_URL,
)


@pytest.fixture(scope="session")
def rpm_publication_api(rpm_client):
    """Fixture for RPM publication API."""
    return PublicationsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_repository_version_api(rpm_client):
    """Fixture for the RPM repository versions API."""
    return RepositoriesRpmVersionsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_distribution_api(rpm_client):
    """Fixture for RPM distribution API."""
    return DistributionsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_client(bindings_cfg):
    """Fixture for RPM client."""
    return RpmApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def rpm_content_repometadata_files_api(rpm_client):
    return ContentRepoMetadataFilesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_rpmremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_repository_api(rpm_client):
    """Fixture for RPM repositories API."""
    return RepositoriesRpmApi(rpm_client)


@pytest.fixture(scope="class")
def rpm_repository_factory(rpm_repository_api, gen_object_with_cleanup):
    """A factory to generate an RPM Repository with auto-deletion after the test run."""

    def _rpm_repository_factory(pulp_domain=None, **body):
        data = {"name": str(uuid.uuid4())}
        data.update(body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_repository_api, data, **kwargs)

    return _rpm_repository_factory


@pytest.fixture(scope="class")
def rpm_rpmremote_factory(rpm_rpmremote_api, gen_object_with_cleanup):
    """A factory to generate an RPM Remote with auto-deletion after the test run."""

    def _rpm_rpmremote_factory(
        *, url=RPM_UNSIGNED_FIXTURE_URL, policy="immediate", pulp_domain=None, **body
    ):
        data = {"url": url, "policy": policy, "name": str(uuid.uuid4())}
        data.update(body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_rpmremote_api, data, **kwargs)

    return _rpm_rpmremote_factory


@pytest.fixture(scope="class")
def rpm_distribution_factory(rpm_distribution_api, gen_object_with_cleanup):
    """A factory to generate an RPM Distribution with auto-deletion after the test run."""

    def _rpm_distribution_factory(pulp_domain=None, **body):
        data = {"base_path": str(uuid.uuid4()), "name": str(uuid.uuid4())}
        data.update(body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_distribution_api, data, **kwargs)

    return _rpm_distribution_factory


@pytest.fixture(scope="class")
def rpm_publication_factory(rpm_publication_api, gen_object_with_cleanup):
    """A factory to generate an RPM Publication with auto-deletion after the test run."""

    def _rpm_publication_factory(pulp_domain=None, **body):
        # XOR check on repository and repository_version
        assert bool("repository" in body) ^ bool("repository_version" in body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_publication_api, body, **kwargs)

    return _rpm_publication_factory


@pytest.fixture(scope="class")
def init_and_sync(rpm_repository_factory, rpm_repository_api, rpm_rpmremote_factory, monitor_task):
    """Initialize a new repository and remote and sync the content from the passed URL."""

    def _init_and_sync(
        repository=None,
        remote=None,
        url=RPM_UNSIGNED_FIXTURE_URL,
        policy="immediate",
        sync_policy="additive",
        skip_types=None,
        optimize=True,
        return_task=False,
    ):
        if repository is None:
            repository = rpm_repository_factory()
        if remote is None:
            remote = rpm_rpmremote_factory(url=url, policy=policy)

        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href,
            sync_policy=sync_policy,
            skip_types=skip_types,
            optimize=optimize,
        )
        sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)

        repository = rpm_repository_api.read(repository.pulp_href)
        return (repository, remote) if not return_task else (repository, remote, task)

    return _init_and_sync
