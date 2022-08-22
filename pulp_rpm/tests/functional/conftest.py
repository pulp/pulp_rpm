import pytest

from pulpcore.client.pulp_rpm import (
    ApiClient as RpmApiClient,
    ContentAdvisoriesApi,
    ContentPackagecategoriesApi,
    ContentPackagegroupsApi,
    ContentPackagelangpacksApi,
    ContentPackagesApi,
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RemotesUlnApi,
    RepositoriesRpmApi,
)

from pulp_smash.pulp3.bindings import delete_orphans


@pytest.fixture(scope="session")
def rpm_client(bindings_cfg):
    """Fixture for RPM client."""
    return RpmApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def rpm_repository_api(rpm_client):
    """Fixture for RPM repositories API."""
    return RepositoriesRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_rpmremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_ulnremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesUlnApi(rpm_client)


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


# This will appear in pulpcore in higher versions
@pytest.fixture
def delete_orphans_pre(request):
    if request.node.get_closest_marker("parallel") is not None:
        raise pytest.UsageError("This test is not suitable to be marked parallel.")
    delete_orphans()
    yield
