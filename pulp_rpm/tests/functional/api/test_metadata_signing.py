import pysequoia
import pytest
import requests

from pulp_rpm.tests.functional.conftest import (
    create_signing_service,
    import_signing_key,
    make_signing_script,
    remove_signing_service,
)
from pulp_rpm.tests.functional.constants import (
    KEY_V4_RSA2K,
    KEY_V4_RSA4K,
    KEY_V6_MLDSA65_ED25519,
    RPM_UNSIGNED_FIXTURE_URL,
)


@pytest.fixture
def metadata_signing_service(request, tmp_path, pulpcore_bindings):
    """Create a metadata signing service for the given (key, backend) pair."""
    key, backend = request.param
    home = tmp_path / "signing"
    home.mkdir(mode=0o700)

    _, fingerprint, _ = import_signing_key(key.private_url, home, backend=backend)
    script_path = make_signing_script(home, fingerprint, tmp_path, backend=backend)
    service_name = create_signing_service(home, fingerprint, script_path, backend=backend)

    service = pulpcore_bindings.SigningServicesApi.list(name=service_name).results[0]
    yield service, key
    remove_signing_service(service_name)


@pytest.mark.parallel
@pytest.mark.parametrize(
    "metadata_signing_service",
    [
        (KEY_V4_RSA4K, "gpg"),
        (KEY_V6_MLDSA65_ED25519, "sq"),
    ],
    indirect=True,
)
def test_publish_signed_repo_metadata(
    metadata_signing_service,
    rpm_repository_factory,
    init_and_sync,
    rpm_publication_factory,
    rpm_distribution_factory,
    distribution_base_url,
):
    """Verify that publishing with a metadata signing service produces a signed repomd.xml.

    After syncing and publishing with a metadata signing service attached, the
    distribution should serve `repomd.xml.asc` (detached signature) and
    `repomd.xml.key` (public key) alongside `repomd.xml`, and the
    detached signature should be verifiable with the published public key.
    """
    service, _key = metadata_signing_service

    repo = rpm_repository_factory(metadata_signing_service=service.pulp_href)
    repo, _ = init_and_sync(
        repository=repo,
        url=RPM_UNSIGNED_FIXTURE_URL,
        policy="on_demand",
    )

    publication = rpm_publication_factory(repository=repo.pulp_href)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)
    base_url = distribution_base_url(distribution.base_url)

    repomd_resp = requests.get(f"{base_url}/repodata/repomd.xml")
    assert repomd_resp.status_code == 200

    asc_resp = requests.get(f"{base_url}/repodata/repomd.xml.asc")
    assert asc_resp.status_code == 200
    assert len(asc_resp.content) > 0, "repomd.xml.asc is empty"

    key_resp = requests.get(f"{base_url}/repodata/repomd.xml.key")
    assert key_resp.status_code == 200
    assert len(key_resp.content) > 0, "repomd.xml.key is empty"

    # Verify the detached signature using pysequoia
    cert = pysequoia.Cert.from_bytes(key_resp.content)
    sig = pysequoia.Sig.from_bytes(asc_resp.content)
    pysequoia.verify(
        bytes=repomd_resp.content,
        signature=sig,
        store=lambda _key_ids: [cert],
    )


@pytest.fixture
def two_key_signing_service(tmp_path, pulpcore_bindings):
    """A signing service created with KEY_V4_RSA4K, whose keyring also holds KEY_V4_RSA2K."""
    home = tmp_path / "signing"
    home.mkdir(mode=0o700)

    _, service_fingerprint, _ = import_signing_key(KEY_V4_RSA4K.private_url, home)
    _, other_fingerprint, _ = import_signing_key(KEY_V4_RSA2K.private_url, home)
    script_path = make_signing_script(home, service_fingerprint, tmp_path)
    service_name = create_signing_service(home, service_fingerprint, script_path)

    service = pulpcore_bindings.SigningServicesApi.list(name=service_name).results[0]
    yield service, other_fingerprint
    remove_signing_service(service_name)


@pytest.mark.parallel
def test_publish_with_metadata_signing_fingerprint(
    two_key_signing_service,
    rpm_repository_factory,
    init_and_sync,
    rpm_publication_factory,
    rpm_distribution_factory,
    distribution_base_url,
):
    """Verify that a repository signs repomd.xml with its own fingerprint.

    The signature must verify against the repository's key rather than the one the signing
    service was created with. Since the service only stores the public key of its own key,
    `repomd.xml.key` is not published at all.
    """
    service, other_fingerprint = two_key_signing_service

    repo = rpm_repository_factory(
        metadata_signing_service=service.pulp_href,
        metadata_signing_fingerprint=other_fingerprint,
    )
    repo, _ = init_and_sync(
        repository=repo,
        url=RPM_UNSIGNED_FIXTURE_URL,
        policy="on_demand",
    )

    publication = rpm_publication_factory(repository=repo.pulp_href)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)
    base_url = distribution_base_url(distribution.base_url)

    repomd_resp = requests.get(f"{base_url}/repodata/repomd.xml")
    assert repomd_resp.status_code == 200

    asc_resp = requests.get(f"{base_url}/repodata/repomd.xml.asc")
    assert asc_resp.status_code == 200

    # Only the overriding key is offered, so this fails if the service's key was used instead.
    cert = pysequoia.Cert.from_bytes(requests.get(KEY_V4_RSA2K.public_url).content)
    pysequoia.verify(
        bytes=repomd_resp.content,
        signature=pysequoia.Sig.from_bytes(asc_resp.content),
        store=lambda _key_ids: [cert],
    )

    assert requests.get(f"{base_url}/repodata/repomd.xml.key").status_code == 404
