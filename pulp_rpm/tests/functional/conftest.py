import hashlib
import json
import uuid
from tempfile import NamedTemporaryFile

import pytest
import requests

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
    RpmRepositorySyncURL,
)

from pulp_rpm.tests.functional.constants import (
    BASE_TEST_JSON,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_SIGNED_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_SIGNED_FIXTURE_URL,
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
def signed_artifact(artifacts_api_client, tmp_path):
    data = requests.get(RPM_SIGNED_URL).content
    artifacts = artifacts_api_client.list(sha256=hashlib.sha256(data).hexdigest(), limit=1)
    try:
        return artifacts.results[0].to_dict()
    except IndexError:
        pass

    temp_file = tmp_path / str(uuid.uuid4())
    temp_file.write_bytes(data)
    return artifacts_api_client.create(temp_file).to_dict()


@pytest.fixture
def rpm_artifact_factory(
    artifacts_api_client, gen_object_with_cleanup, pulp_domain_enabled, tmp_path
):
    """Return an artifact created from uploading an RPM file."""

    def _rpm_artifact_factory(url=RPM_SIGNED_URL, pulp_domain=None):
        temp_file = tmp_path / str(uuid.uuid4())
        temp_file.write_bytes(requests.get(url).content)
        kwargs = {}
        if pulp_domain:
            if not pulp_domain_enabled:
                raise RuntimeError("Server does not have domains enabled.")
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(artifacts_api_client, temp_file, **kwargs)

    return _rpm_artifact_factory


@pytest.fixture
def rpm_package_factory(
    gen_object_with_cleanup,
    pulp_domain_enabled,
    rpm_package_api,
):
    """Return a Package created from uploading an RPM file."""

    def _rpm_package_factory(url=RPM_SIGNED_URL, pulp_domain=None):
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(requests.get(url).content)
            file_to_upload.flush()
            upload_attrs = {"file": file_to_upload.name}

            kwargs = {}
            if pulp_domain:
                if not pulp_domain_enabled:
                    raise RuntimeError("Server does not have domains enabled.")
                kwargs["pulp_domain"] = pulp_domain

            return gen_object_with_cleanup(rpm_package_api, **upload_attrs, **kwargs)

    return _rpm_package_factory


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


@pytest.fixture
def upload_wrong_file_type(rpm_advisory_api):
    def _upload(remote_path):
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(requests.get(remote_path).content)
            file_to_upload.flush()
            upload_attrs = {"file": file_to_upload.name}
            return rpm_advisory_api.create(**upload_attrs)

    return _upload


@pytest.fixture
def upload_advisory_factory(
    add_to_cleanup,
    monitor_task,
    pulp_domain_enabled,
    rpm_advisory_api,
):
    """Upload advisory from a json file, return advisory, vers_href, and id-used."""

    def _upload_advisory_factory(
        advisory=BASE_TEST_JSON, repository=None, pulp_domain=None, set_id=False, use_id=None
    ):
        kwargs = {}
        if pulp_domain:
            if not pulp_domain_enabled:
                raise RuntimeError("Server does not have domains enabled.")
            kwargs["pulp_domain"] = pulp_domain

        with NamedTemporaryFile("w+") as file_to_upload:
            json_advisory = json.loads(advisory)
            if set_id or use_id:
                json_advisory["id"] = use_id if use_id else str(uuid.uuid4())
            used_id = json_advisory["id"]
            json.dump(json_advisory, file_to_upload)
            file_to_upload.flush()
            upload_attrs = {"file": file_to_upload.name}
            if repository:
                upload_attrs["repository"] = repository.pulp_href
            file_to_upload.flush()
            response = rpm_advisory_api.create(**upload_attrs, **kwargs)

        task_rslt = monitor_task(response.task)
        if repository:
            assert 2 == len(task_rslt.created_resources)
        else:
            assert 1 == len(task_rslt.created_resources)

        vers_href = None
        advisory_href = None
        for rsrc in task_rslt.created_resources:
            if "versions" in rsrc:
                vers_href = rsrc
            elif "advisories" in rsrc:
                advisory_href = rsrc
        assert advisory_href

        add_to_cleanup(rpm_advisory_api, advisory_href)
        entity = rpm_advisory_api.read(advisory_href)
        return entity, vers_href, used_id

    return _upload_advisory_factory


@pytest.fixture
def assert_uploaded_advisory(rpm_advisory_api):
    """List advisories for a given version-href, and assert that the specified ID is therein."""

    def _from_results(advisory_id, vers_href):
        advisories = rpm_advisory_api.list(id=advisory_id, repository_version=vers_href)
        assert 1 == len(advisories.results)
        return advisories.results[0].pulp_href, vers_href

    return _from_results


@pytest.fixture
def setup_domain(
    gen_object_with_cleanup, domains_api_client, rpm_rpmremote_api, rpm_repository_api, monitor_task
):
    def _setup_domain(sync=True, url=RPM_SIGNED_FIXTURE_URL, pulp_domain=None):
        if not pulp_domain:
            body = {
                "name": str(uuid.uuid4()),
                "storage_class": "pulpcore.app.models.storage.FileSystem",
                "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
            }
            pulp_domain = gen_object_with_cleanup(domains_api_client, body)

        remote = gen_object_with_cleanup(
            rpm_rpmremote_api, {"name": str(uuid.uuid4()), "url": url}, pulp_domain=pulp_domain.name
        )
        src = gen_object_with_cleanup(
            rpm_repository_api,
            {"name": str(uuid.uuid4()), "remote": remote.pulp_href},
            pulp_domain=pulp_domain.name,
        )

        if sync:
            sync_url = RpmRepositorySyncURL()
            monitor_task(rpm_repository_api.sync(src.pulp_href, sync_url).task)
            src = rpm_repository_api.read(src.pulp_href)

        dest = gen_object_with_cleanup(
            rpm_repository_api, {"name": str(uuid.uuid4())}, pulp_domain=pulp_domain.name
        )
        return pulp_domain, remote, src, dest

    return _setup_domain


@pytest.fixture
def cleanup_domains(orphans_cleanup_api_client, monitor_task, rpm_repository_api):
    def _cleanup_domains(
        domains,
        content_api_client=None,
        cleanup_repositories=False,
        repository_api_client=rpm_repository_api,
    ):
        for domain in domains:
            # clean up each domain specified
            if domain:
                if cleanup_repositories:
                    # Delete repos from the domain
                    for repo in repository_api_client.list(pulp_domain=domain.name).results:
                        monitor_task(repository_api_client.delete(repo.pulp_href).task)
                # Let orphan-cleanup reap the resulting abandoned content
                monitor_task(
                    orphans_cleanup_api_client.cleanup(
                        {"orphan_protection_time": 0}, pulp_domain=domain.name
                    ).task
                )

        if content_api_client:
            # IF we have a client, check that each domain is empty of that kind-of entity
            for domain in domains:
                if domain:
                    assert content_api_client.list(pulp_domain=domain.name).count == 0

    return _cleanup_domains
