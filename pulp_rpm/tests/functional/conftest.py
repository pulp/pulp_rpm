import pytest

from pulpcore.client.pulp_rpm import (
    AcsRpmApi,
    ApiClient as RpmApiClient,
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RemotesUlnApi,
    RepositoriesRpmApi,
)


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
