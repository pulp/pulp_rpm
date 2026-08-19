import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import requests

from pulpcore.client.pulp_rpm import (
    AcsRpmApi,
    ContentAdvisoriesApi,
    ContentDistributionTreesApi,
    ContentModulemdDefaultsApi,
    ContentModulemdObsoletesApi,
    ContentModulemdsApi,
    ContentPackagecategoriesApi,
    ContentPackagegroupsApi,
    ContentPackagelangpacksApi,
    RemotesUlnApi,
    RepositoriesRpmVersionsApi,
    RpmCompsApi,
    RpmCopyApi,
    RpmRepositorySyncURL,
)

from pulp_rpm.tests.functional.constants import (
    BASE_TEST_JSON,
    KEY_V4_RSA4K,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_SIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import (
    Nevra,
    PackageListFetcher,
    RepositoryBuilder,
    build_rpm,
    fetch_url,
)


@pytest.fixture(scope="session")
def rpm_ulnremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesUlnApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_acs_api(rpm_client):
    """Fixture for RPM alternate content source API."""
    return AcsRpmApi(rpm_client)


@pytest.fixture
def package_listing(rpm_package_api):
    """Fixture returning a PackageListFetcher with access to the packages API."""
    return PackageListFetcher(rpm_package_api=rpm_package_api)


@pytest.fixture
def repository_builder(tmp_path):
    return RepositoryBuilder(tmp_path=tmp_path)


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


@pytest.fixture(scope="session")
def rpm_repository_versions_api(rpm_client):
    return RepositoriesRpmVersionsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_key_bytes():
    """Session-scoped cache of fetched signing-key bytes, keyed by URL.

    Prevents the same public/private key file from being downloaded once per test.
    """
    cache = {}

    def _fetch(url):
        if url not in cache:
            cache[url] = fetch_url(url)
        return cache[url]

    return _fetch


@pytest.fixture(scope="session")
def rpm_signer_factory(rpm_key_bytes):
    """Return a factory building an `rpm_rs.Signer`.

    By default the factory takes a `FixtureKey` (default `KEY_V4_RSA4K`) and returns
    `(signer, "<version>:<FINGERPRINT>")` so the detected `signing_keys` is predictable.

    Pass `signing_algorithm` (a `pysequoia.SigningAlgorithm`) to instead generate a
    fresh RFC 9580 key in-place. This is useful for PQC (e.g. ML-DSA) tests that need
    a unique fingerprint to avoid collisions with other tests reusing a static fixture
    key. The fingerprint isn't known ahead of time, so `None` is returned in its place.
    """
    import rpm_rs

    def _factory(key=KEY_V4_RSA4K, *, signing_algorithm=None):
        if signing_algorithm is not None:
            from pysequoia import Profile, Tsk

            tsk = Tsk.generate(profile=Profile.RFC9580, signing_algorithm=signing_algorithm)
            # rpm_rs.Signer expects ASCII-armored bytes
            return rpm_rs.Signer(str(tsk).encode()), None
        signer = rpm_rs.Signer(rpm_key_bytes(key.private_url))
        return signer, f"{key.version}:{key.signing_fingerprint}"

    return _factory


@pytest.fixture(scope="session")
def rpm_signer(rpm_signer_factory):
    """A session-scoped signer using the v4 RSA4k fixture key. See `rpm_signer_factory`."""
    return rpm_signer_factory()


@pytest.fixture(scope="session")
def rpm_verifier_factory(rpm_key_bytes):
    """Return a factory building an `rpm_rs.Verifier` from fixture key constants.

    Accepts one or more `FixtureKey` objects so a single verifier can validate
    artifacts carrying multiple signatures. Public keys are fetched once per
    session and cached.
    """
    import rpm_rs

    def _factory(*keys):
        verifier = rpm_rs.Verifier()
        for key in keys:
            verifier.load_from_asc_bytes(rpm_key_bytes(key.public_url))
        return verifier

    return _factory


def _make_rpm_file(tmp_path, url=None):
    """Write an RPM to a temp file; fetch from url if given, otherwise generate one."""
    uid = uuid.uuid4().hex[:8]
    path = tmp_path / f"test-pkg-{uid}-1.0-1.noarch.rpm"
    if url is not None:
        path.write_bytes(fetch_url(url))
    else:
        build_rpm(Nevra(f"test-pkg-{uid}", 0, "1.0", "1", "noarch"), path)
    return path


@pytest.fixture
def rpm_artifact_factory(pulpcore_bindings, gen_object_with_cleanup, pulp_domain_enabled, tmp_path):
    """Return an artifact created from uploading an RPM file."""

    def _rpm_artifact_factory(url=None, pulp_domain=None):
        rpm_file = _make_rpm_file(tmp_path, url)
        kwargs = {}
        if pulp_domain:
            if not pulp_domain_enabled:
                raise RuntimeError("Server does not have domains enabled.")
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(pulpcore_bindings.ArtifactsApi, str(rpm_file), **kwargs)

    return _rpm_artifact_factory


@pytest.fixture
def rpm_create_package(tmp_path):
    """Return a factory that builds a minimal RPM file and returns its path."""

    def _factory(nevra: Nevra) -> Path:
        path = tmp_path / f"{nevra.to_nvra()}.rpm"
        build_rpm(nevra, path)
        return path

    return _factory


@pytest.fixture
def rpm_package_factory(
    gen_object_with_cleanup,
    pulp_domain_enabled,
    rpm_package_api,
    tmp_path,
):
    """Return a Package created from uploading an RPM file."""

    def _rpm_package_factory(url=None, pulp_domain=None):
        rpm_file = _make_rpm_file(tmp_path, url)
        upload_attrs = {"file": str(rpm_file)}

        kwargs = {}
        if pulp_domain:
            if not pulp_domain_enabled:
                raise RuntimeError("Server does not have domains enabled.")
            kwargs["pulp_domain"] = pulp_domain

        return gen_object_with_cleanup(rpm_package_api, **upload_attrs, **kwargs)

    return _rpm_package_factory


@pytest.fixture
def pulpcore_chunked_file_factory(tmp_path):
    """Returns a function to create chunks from a file to be uploaded."""

    def _create_chunks(upload_path, chunk_size=512):
        chunks = {"chunks": []}
        hasher = hashlib.new("sha256")
        start = 0
        with open(upload_path, "rb") as f:
            data = f.read()
        chunks["size"] = len(data)

        while start < len(data):
            content = data[start : start + chunk_size]
            chunk_file = tmp_path / str(uuid.uuid4())
            hasher.update(content)
            chunk_file.write_bytes(content)
            content_sha = hashlib.sha256(content).hexdigest()
            end = start + len(content) - 1
            chunks["chunks"].append(
                (str(chunk_file), f"bytes {start}-{end}/{chunks['size']}", content_sha)
            )
            start += len(content)
        chunks["digest"] = hasher.hexdigest()
        return chunks

    return _create_chunks


@pytest.fixture
def pulpcore_upload_chunks(pulpcore_bindings, gen_object_with_cleanup):
    """Upload file in chunks and return the Upload object."""

    def _upload_chunks(size, chunks, sha256):
        upload = gen_object_with_cleanup(pulpcore_bindings.UploadsApi, {"size": size})
        for chunk_file, content_range, chunk_sha in chunks:
            pulpcore_bindings.UploadsApi.update(
                upload_href=upload.pulp_href,
                file=chunk_file,
                content_range=content_range,
                sha256=chunk_sha,
            )
        return upload

    yield _upload_chunks


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
def rpm_metadata_signing_service(pulpcore_bindings, tmp_path_factory):
    """Session-scoped GPG-based metadata signing service using KEY_V4_RSA4K."""
    home = tmp_path_factory.mktemp("metadata_signing_gpg")
    _, fingerprint, _ = import_signing_key(KEY_V4_RSA4K.private_url, home, backend="gpg")
    script_path = make_signing_script(home, fingerprint, backend="gpg")
    service_name = create_signing_service(home, fingerprint, script_path, backend="gpg")

    results = pulpcore_bindings.SigningServicesApi.list(name=service_name)
    return results.results[0] if results.count == 1 else None


@pytest.fixture
def upload_wrong_file_type(rpm_advisory_api):
    def _upload(remote_path):
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(fetch_url(remote_path))
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
    gen_object_with_cleanup, pulpcore_bindings, rpm_rpmremote_api, rpm_repository_api, monitor_task
):
    def _setup_domain(sync=True, url=RPM_SIGNED_FIXTURE_URL, pulp_domain=None):
        if not pulp_domain:
            body = {
                "name": str(uuid.uuid4()),
                "storage_class": "pulpcore.app.models.storage.FileSystem",
                "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
            }
            pulp_domain = gen_object_with_cleanup(pulpcore_bindings.DomainsApi, body)

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
def cleanup_domains(pulpcore_bindings, monitor_task, rpm_repository_api):
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
                    pulpcore_bindings.OrphansCleanupApi.cleanup(
                        {"orphan_protection_time": 0}, pulp_domain=domain.name
                    ).task
                )

        if content_api_client:
            # IF we have a client, check that each domain is empty of that kind-of entity
            for domain in domains:
                if domain:
                    assert content_api_client.list(pulp_domain=domain.name).count == 0

    return _cleanup_domains


SIGNING_SCRIPT_STRING = """#!/usr/bin/env bash

FILE_PATH=$1
SIGNATURE_PATH="$1.asc"

GPG_KEY_ID="{gpg_key_id}"

# Create a detached signature
gpg --quiet --batch --homedir {gpg_home} --detach-sign --local-user "${{GPG_KEY_ID}}" \\
   --armor --output ${{SIGNATURE_PATH}} ${{FILE_PATH}}

# Check the exit status
STATUS=$?
if [[ ${{STATUS}} -eq 0 ]]; then
   echo '{{"file": "'${{FILE_PATH}}'", "signature": "'${{SIGNATURE_PATH}}'"}}'
else
   exit ${{STATUS}}
fi
"""

SQ_SIGNING_SCRIPT_STRING = """#!/usr/bin/env bash

FILE_PATH=$1
SIGNATURE_PATH="$1.asc"

SQ_HOME="{sq_home}"
SIGNER="{signer_fingerprint}"

# Create a detached signature using Sequoia (sq)
sq --home "${{SQ_HOME}}" sign --signer "${{SIGNER}}" \\
   --signature-file="${{SIGNATURE_PATH}}" "${{FILE_PATH}}"

# Check the exit status
STATUS=$?
if [[ ${{STATUS}} -eq 0 ]]; then
   echo '{{"file": "'${{FILE_PATH}}'", "signature": "'${{SIGNATURE_PATH}}'"}}'
else
   exit ${{STATUS}}
fi
"""


def import_signing_key(key_url, home, *, backend="gpg"):
    """Import a PGP key into a keyring and return metadata.

    Returns ``(gpg_instance_or_none, fingerprint, keyid)``.
    The first element is a ``gnupg.GPG`` instance when *backend* is ``"gpg"``,
    or ``None`` when *backend* is ``"sq"``.
    """
    response = requests.get(key_url)
    response.raise_for_status()

    if backend == "sq":
        from pysequoia import Cert

        completed = subprocess.run(
            ("sq", "--home", str(home), "key", "import"),
            input=response.content,
            capture_output=True,
        )
        assert completed.returncode == 0, completed.stderr.decode()

        cert = Cert.from_bytes(response.content)
        fingerprint = cert.fingerprint.upper()
        keyid = fingerprint[-16:]

        return None, fingerprint, keyid
    else:
        try:
            import gnupg
        except ImportError:
            pytest.skip("python-gnupg not installed")

        gpg = gnupg.GPG(gnupghome=home)

        result = gpg.import_keys(response.content)
        assert result.count >= 1, f"Failed to import key from {key_url}"

        key_info = gpg.list_keys()[0]
        fingerprint = key_info["fingerprint"]
        keyid = key_info["keyid"]
        gpg.trust_keys(fingerprint, "TRUST_ULTIMATE")

        return gpg, fingerprint, keyid


def make_signing_script(home, fingerprint, script_dir=None, *, backend="gpg"):
    """Create a detached-signature signing script.

    Returns the script path.
    """
    if script_dir is None:
        script_dir = home
    if backend == "sq":
        script_path = script_dir / "sq_sign.sh"
        script_path.write_text(
            SQ_SIGNING_SCRIPT_STRING.format(sq_home=home, signer_fingerprint=fingerprint)
        )
    else:
        script_path = script_dir / "sign.sh"
        script_path.write_text(SIGNING_SCRIPT_STRING.format(gpg_home=home, gpg_key_id=fingerprint))
    script_path.chmod(0o755)
    return script_path


def create_signing_service(
    home,
    fingerprint,
    script_path,
    *,
    backend="gpg",
    service_class="core:AsciiArmoredDetachedSigningService",
):
    """Register a signing service via pulpcore-manager.

    Returns the service name.
    """
    service_name = str(uuid.uuid4())
    cmd = [
        "pulpcore-manager",
        "add-signing-service",
        service_name,
        str(script_path),
        fingerprint,
        "--class",
        service_class,
        "--backend",
        backend,
        "--gnupghome",
        str(home),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr

    return service_name


def remove_signing_service(service_name, service_class="core:AsciiArmoredDetachedSigningService"):
    """Remove a signing service created by ``create_signing_service``."""
    subprocess.run(
        (
            "pulpcore-manager",
            "remove-signing-service",
            service_name,
            "--class",
            service_class,
        ),
        capture_output=True,
    )
