import uuid

import pytest

from pulpcore.client.pulp_rpm import (
    AcsRpmApi,
    ApiClient as RpmApiClient,
    ContentAdvisoriesApi,
    ContentDistributionTreesApi,
    ContentPackagecategoriesApi,
    ContentPackagegroupsApi,
    ContentPackagelangpacksApi,
    ContentPackagesApi,
    DistributionsRpmApi,
    ContentModulemdsApi,
    ContentModulemdDefaultsApi,
    ContentModulemdObsoletesApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RemotesUlnApi,
    RepositoriesRpmApi,
    RepositoriesRpmVersionsApi,
    RpmCopyApi,
    RpmCompsApi,
    RpmRepositorySyncURL,
)

from pulp_rpm.tests.functional.constants import RPM_UNSIGNED_FIXTURE_URL, RPM_KICKSTART_FIXTURE_URL
from pulp_rpm.tests.functional.utils import init_signed_repo_configuration


@pytest.fixture(scope="session")
def rpm_client(bindings_cfg):
    """Fixture for RPM client."""
    return RpmApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def rpm_repository_api(rpm_client):
    """Fixture for RPM repositories API."""
    return RepositoriesRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_repository_version_api(rpm_client):
    """Fixture for the RPM repository versions API."""
    return RepositoriesRpmVersionsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_rpmremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_ulnremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesUlnApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_acs_api(rpm_client):
    """Fixture for RPM alternate content source API."""
    return AcsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_publication_api(rpm_client):
    """Fixture for RPM publication API."""
    return PublicationsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_distribution_api(rpm_client):
    """Fixture for RPM distribution API."""
    return DistributionsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_package_api(rpm_client):
    """Fixture for RPM distribution API."""
    return ContentPackagesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_advisory_api(rpm_client):
    """Fixture for RPM distribution API."""
    return ContentAdvisoriesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_package_category_api(rpm_client):
    """Fixture for RPM distribution API."""
    return ContentPackagecategoriesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_package_groups_api(rpm_client):
    """Fixture for RPM distribution API."""
    return ContentPackagegroupsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_package_lang_packs_api(rpm_client):
    """Fixture for RPM distribution API."""
    return ContentPackagelangpacksApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_modulemd_api(rpm_client):
    """Fixture for RPM Modulemd API."""
    return ContentModulemdsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_modulemd_defaults_api(rpm_client):
    """Fixture for RPM ModulemdDefault API."""
    return ContentModulemdDefaultsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_modulemd_obsoletes_api(rpm_client):
    """Fixture for RPM ModulemdObsolete API."""
    return ContentModulemdObsoletesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_comps_api(rpm_client):
    """Fixture for RPM Comps API."""
    return RpmCompsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_content_distribution_trees_api(rpm_client):
    return ContentDistributionTreesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_copy_api(rpm_client):
    return RpmCopyApi(rpm_client)


@pytest.fixture(scope="class")
def rpm_repository_factory(rpm_repository_api, gen_object_with_cleanup):
    """A factory to generate an RPM Repository with auto-deletion after the test run."""

    def _rpm_repository_factory(**kwargs):
        data = {"name": str(uuid.uuid4())}
        data.update(kwargs)
        return gen_object_with_cleanup(rpm_repository_api, data)

    return _rpm_repository_factory


@pytest.fixture(scope="class")
def rpm_rpmremote_factory(rpm_rpmremote_api, gen_object_with_cleanup):
    """A factory to generate an RPM Remote with auto-deletion after the test run."""

    def _rpm_rpmremote_factory(*, url=RPM_UNSIGNED_FIXTURE_URL, policy="immediate", **kwargs):
        data = {"url": url, "policy": policy, "name": str(uuid.uuid4())}
        data.update(kwargs)
        return gen_object_with_cleanup(rpm_rpmremote_api, data)

    return _rpm_rpmremote_factory


@pytest.fixture(scope="class")
def rpm_publication_factory(rpm_publication_api, gen_object_with_cleanup):
    """A factory to generate an RPM Publication with auto-deletion after the test run."""

    def _rpm_publication_factory(**kwargs):
        # XOR check on repository and repository_version
        assert bool("repository" in kwargs) ^ bool("repository_version" in kwargs)
        return gen_object_with_cleanup(rpm_publication_api, kwargs)

    return _rpm_publication_factory


@pytest.fixture(scope="class")
def rpm_distribution_factory(rpm_distribution_api, gen_object_with_cleanup):
    """A factory to generate an RPM Distribution with auto-deletion after the test run."""

    def _rpm_distribution_factory(**kwargs):
        data = {"base_path": str(uuid.uuid4()), "name": str(uuid.uuid4())}
        data.update(kwargs)
        return gen_object_with_cleanup(rpm_distribution_api, data)

    return _rpm_distribution_factory


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


@pytest.fixture(scope="class")
def rpm_unsigned_repo_immediate(init_and_sync):
    repo, _ = init_and_sync()
    return repo


@pytest.fixture(scope="class")
def rpm_unsigned_repo_on_demand(init_and_sync):
    repo, _ = init_and_sync(policy="on_demand")
    return repo


@pytest.fixture(scope="class")
def rpm_kickstart_repo_immediate(init_and_sync):
    repo, _ = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL)
    return repo


@pytest.fixture(scope="session")
def rpm_metadata_signing_service(signing_service_api_client):
    results = signing_service_api_client.list(name="sign-metadata")
    signing_service = None
    if results.count == 0:
        result = init_signed_repo_configuration()
        if result.returncode == 0:
            results = signing_service_api_client.list(name="sign-metadata")
    if results.count == 1:
        signing_service = results.results[0]

    return signing_service
