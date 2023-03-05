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
    PublicationsRpmApi,
    RemotesRpmApi,
    RemotesUlnApi,
    RepositoriesRpmApi,
    RepositoriesRpmVersionsApi,
    RpmCopyApi,
    RpmRepositorySyncURL,
)

from pulp_rpm.tests.functional.constants import RPM_UNSIGNED_FIXTURE_URL, RPM_KICKSTART_FIXTURE_URL

IMPORT_EXPORT_NUM_REPOS = 2


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
    ):
        if repository is None:
            repository = rpm_repository_factory()
        if remote is None:
            remote = rpm_rpmremote_factory(url=url, policy=policy)

        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href, sync_policy=sync_policy, skip_types=skip_types
        )
        sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        repository = rpm_repository_api.read(repository.pulp_href)
        return repository, remote

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


@pytest.fixture
def import_export_repositories(
    rpm_repository_api,
    rpm_repository_factory,
    rpm_rpmremote_factory,
    monitor_task,
):
    """Create and sync a number of repositories to be exported."""

    def _import_export_repositories(
        import_repos=None, export_repos=None, url=RPM_UNSIGNED_FIXTURE_URL
    ):
        if import_repos or export_repos:
            # repositories were initialized by the caller
            return import_repos, export_repos

        import_repos = []
        export_repos = []
        for r in range(IMPORT_EXPORT_NUM_REPOS):
            import_repo = rpm_repository_factory()
            export_repo = rpm_repository_factory()

            remote = rpm_rpmremote_factory(url=url)
            repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
            sync_response = rpm_repository_api.sync(export_repo.pulp_href, repository_sync_data)
            monitor_task(sync_response.task)

            # remember it
            import_repo = rpm_repository_api.read(import_repo.pulp_href)
            export_repo = rpm_repository_api.read(export_repo.pulp_href)
            export_repos.append(export_repo)
            import_repos.append(import_repo)
        return import_repos, export_repos

    return _import_export_repositories


@pytest.fixture
def create_exporter(gen_object_with_cleanup, exporters_pulp_api_client, import_export_repositories):
    def _create_exporter(import_repos=None, export_repos=None, url=RPM_UNSIGNED_FIXTURE_URL):
        if not export_repos:
            _, export_repos = import_export_repositories(import_repos, export_repos, url=url)

        body = {
            "name": str(uuid.uuid4()),
            "repositories": [r.pulp_href for r in export_repos],
            "path": f"/tmp/{uuid.uuid4()}/",
        }
        exporter = gen_object_with_cleanup(exporters_pulp_api_client, body)
        return exporter

    return _create_exporter


@pytest.fixture
def create_export(exporters_pulp_exports_api_client, create_exporter, monitor_task):
    def _create_export(
        import_repos=None, export_repos=None, url=RPM_UNSIGNED_FIXTURE_URL, exporter=None
    ):
        if not exporter:
            exporter = create_exporter(import_repos, export_repos, url=url)

        export_response = exporters_pulp_exports_api_client.create(exporter.pulp_href, {})
        export_href = monitor_task(export_response.task).created_resources[0]
        export = exporters_pulp_exports_api_client.read(export_href)
        return export

    return _create_export
