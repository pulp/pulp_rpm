import uuid

import pytest

from pulpcore.client.pulp_rpm import (
    AcsRpmApi,
    ContentAdvisoriesApi,
    ContentDistributionTreesApi,
    ContentPackagecategoriesApi,
    ContentPackagegroupsApi,
    ContentPackagelangpacksApi,
    ContentPackagesApi,
    ContentModulemdsApi,
    ContentModulemdDefaultsApi,
    ContentModulemdObsoletesApi,
    RemotesUlnApi,
    RpmCopyApi,
    RpmCompsApi,
)

from pulp_rpm.tests.functional.constants import (
    RPM_KICKSTART_FIXTURE_URL,
    RPM_SIGNED_URL,
    RPM_MODULAR_FIXTURE_URL,
)

from pulp_rpm.tests.functional.utils import init_signed_repo_configuration


@pytest.fixture(scope="session")
def rpm_ulnremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesUlnApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_acs_api(rpm_client):
    """Fixture for RPM alternate content source API."""
    return AcsRpmApi(rpm_client)


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


@pytest.fixture
def signed_artifact(http_get, artifacts_api_client, gen_object_with_cleanup, tmp_path):
    temp_file = tmp_path / str(uuid.uuid4())
    temp_file.write_bytes(http_get(RPM_SIGNED_URL))
    return gen_object_with_cleanup(artifacts_api_client, temp_file).to_dict()


@pytest.fixture(scope="class")
def rpm_unsigned_repo_immediate(init_and_sync):
    repo, _ = init_and_sync()
    return repo


@pytest.fixture(scope="class")
def rpm_unsigned_repo_on_demand(init_and_sync):
    repo, _ = init_and_sync(policy="on_demand")
    return repo


@pytest.fixture(scope="class")
def rpm_modular_repo_on_demand(init_and_sync):
    repo, _ = init_and_sync(url=RPM_MODULAR_FIXTURE_URL, policy="on_demand")
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
