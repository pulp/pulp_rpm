import hashlib
import shutil
import uuid
from pathlib import Path

import pytest
import requests
import rpm_rs

from pulpcore.client.pulp_rpm.exceptions import ApiException
from pulpcore.exceptions.validation import InvalidSignatureError

from pulp_rpm.app.shared_utils import RpmTool
from pulp_rpm.tests.functional.constants import (
    KEY_V4_RSA2K,
    KEY_V4_RSA4K,
    KEY_V6_MLDSA65_ED25519,
    RPM_PACKAGE_FILENAME,
    RPM_PACKAGE_FILENAME2,
    RPM_SIGNED_URL,
    RPM_UNSIGNED_URL,
    RPM_UNSIGNED_URL2,
)
from pulp_rpm.tests.functional.utils import get_package_repo_path


def get_fixture(path: Path, url: str) -> Path:
    path.write_bytes(requests.get(url).content)
    return path


def _sign_package(rpm_path, private_key_url, output=None, key_fpr=None):
    """Sign an RPM in place using rpm_rs with a private key fetched from a URL."""
    output = output or rpm_path
    key_bytes = requests.get(private_key_url).content
    signer = rpm_rs.Signer(key_bytes)
    if key_fpr:
        signer = signer.with_signing_key(key_fpr)
    pkg = rpm_rs.Package.open(rpm_path)
    pkg.sign(signer)
    pkg.write_file(output)


@pytest.mark.parallel
def test_register_rpm_package_signing_service(rpm_package_signing_service):
    """
    Register a sample rpmsign-based signing service and validate it works.
    """
    service = rpm_package_signing_service
    assert "/api/v3/signing-services/" in service.pulp_href


@pytest.fixture
def multi_signed_rpm(tmp_path):
    """Create an RPM signed with two different GPG keys using rpm_rs."""
    rpm_path = tmp_path / "multi-signed.rpm"
    rpm_path.write_bytes(requests.get(RPM_UNSIGNED_URL).content)

    _sign_package(rpm_path, KEY_V4_RSA2K.private_url)
    _sign_package(rpm_path, KEY_V4_RSA4K.private_url)

    return rpm_path


@pytest.fixture
def signing_gpg_extra(signing_gpg_metadata):
    """Import the v4 rsa2k and rsa4k keys into the GPG keyring used by the signing service."""
    gpg, _, _ = signing_gpg_metadata

    for url in (KEY_V4_RSA2K.private_url, KEY_V4_RSA4K.private_url):
        response = requests.get(url)
        response.raise_for_status()
        import_result = gpg.import_keys(response.content)
        gpg.trust_keys(import_result.fingerprints[0], "TRUST_ULTIMATE")

    return KEY_V4_RSA2K, KEY_V4_RSA4K


@pytest.mark.parallel
def test_sign_package_on_upload(
    tmp_path,
    pulpcore_bindings,
    monitor_task,
    gen_object_with_cleanup,
    download_content_unit,
    signing_gpg_extra,
    rpm_package_signing_service,
    rpm_package_api,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_publication_factory,
    rpm_package_factory,
    rpm_distribution_factory,
):
    """
    Sign an Rpm Package with the Package Upload endpoint.
    """
    key_a, key_b = signing_gpg_extra
    fingerprint_set = set([key_a.signing_fingerprint, key_b.signing_fingerprint])
    assert len(fingerprint_set) == 2

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_a.asc", KEY_V4_RSA2K.public_url))
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_b.asc", KEY_V4_RSA4K.public_url))

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_UNSIGNED_URL).content)
    with pytest.raises(InvalidSignatureError, match="The package is not signed: .*"):
        rpm_tool.verify_signature(file_to_upload)

    # Upload Package to Repository
    # The same file is uploaded, but signed with different keys each time
    for fingerprint in fingerprint_set:
        prefixed_fingerprint = f"v4:{fingerprint}"
        repository = rpm_repository_factory(
            package_signing_service=rpm_package_signing_service.pulp_href,
            package_signing_fingerprint=prefixed_fingerprint,
        )
        upload_response = rpm_package_api.create(
            file=str(file_to_upload.absolute()),
            repository=repository.pulp_href,
        )
        package_href = monitor_task(upload_response.task).created_resources[2]
        package = rpm_package_api.read(package_href)
        assert package.signing_keys == [prefixed_fingerprint]

        # Verify that the final served package is signed
        publication = rpm_publication_factory(repository=repository.pulp_href)
        distribution = rpm_distribution_factory(publication=publication.pulp_href)
        downloaded_package = tmp_path / "package.rpm"
        downloaded_package.write_bytes(
            download_content_unit(
                distribution.base_path, get_package_repo_path(package.location_href)
            )
        )
        assert rpm_tool.verify_signature(downloaded_package)

        # Verify signing_key filter
        repository = rpm_repository_api.read(repository.pulp_href)
        assert (
            rpm_package_api.list(
                repository_version=repository.latest_version_href, signing_key=prefixed_fingerprint
            ).count
            == 1
        )


@pytest.fixture
def pulpcore_chunked_file_factory(tmp_path):
    """Returns a function to create chunks from file to be uploaded."""

    def _create_chunks(upload_path, chunk_size=512):
        """Chunks file to be uploaded."""
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
def pulpcore_upload_chunks(
    pulpcore_bindings,
    gen_object_with_cleanup,
    monitor_task,
):
    """Upload file in chunks."""

    def _upload_chunks(size, chunks, sha256, include_chunk_sha256=False):
        """
        Chunks is a list of tuples in the form of (chunk_filename, "bytes-ranges", optional_sha256).
        """
        upload = gen_object_with_cleanup(pulpcore_bindings.UploadsApi, {"size": size})

        for data in chunks:
            kwargs = {"file": data[0], "content_range": data[1], "upload_href": upload.pulp_href}
            if include_chunk_sha256:
                if len(data) != 3:
                    raise Exception(f"Chunk didn't include its sha256: {data}")
                kwargs["sha256"] = data[2]

            pulpcore_bindings.UploadsApi.update(**kwargs)

        return upload

    yield _upload_chunks


@pytest.mark.parallel
def test_sign_chunked_package_on_upload(
    tmp_path,
    pulpcore_bindings,
    monitor_task,
    gen_object_with_cleanup,
    download_content_unit,
    signing_gpg_extra,
    rpm_package_signing_service,
    rpm_package_api,
    rpm_repository_factory,
    rpm_publication_factory,
    rpm_package_factory,
    rpm_distribution_factory,
    pulpcore_upload_chunks,
    pulpcore_chunked_file_factory,
):
    """
    Sign an Rpm Package with the Package Upload endpoint using chunked uploads.
    """
    key_a, key_b = signing_gpg_extra
    fingerprint_set = set([key_a.signing_fingerprint, key_b.signing_fingerprint])
    assert len(fingerprint_set) == 2

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_a.asc", KEY_V4_RSA2K.public_url))
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_b.asc", KEY_V4_RSA4K.public_url))

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME2
    file_to_upload.write_bytes(requests.get(RPM_UNSIGNED_URL2).content)
    with pytest.raises(InvalidSignatureError, match="The package is not signed: .*"):
        rpm_tool.verify_signature(file_to_upload)

    # Upload Package to Repository
    # The same file is uploaded, but signed with different keys each time
    for fingerprint in fingerprint_set:
        prefixed_fingerprint = f"v4:{fingerprint}"
        repository = rpm_repository_factory(
            package_signing_service=rpm_package_signing_service.pulp_href,
            package_signing_fingerprint=prefixed_fingerprint,
        )
        file_chunks_data = pulpcore_chunked_file_factory(file_to_upload)
        size = file_chunks_data["size"]
        chunks = file_chunks_data["chunks"]
        sha256 = file_chunks_data["digest"]

        upload = pulpcore_upload_chunks(size, chunks, sha256, include_chunk_sha256=True)
        upload_response = rpm_package_api.create(
            upload=upload.pulp_href,
            repository=repository.pulp_href,
        )
        package_href = monitor_task(upload_response.task).created_resources[2]
        package = rpm_package_api.read(package_href)
        assert package.signing_keys == [prefixed_fingerprint]

        # Verify that the final served package is signed
        publication = rpm_publication_factory(repository=repository.pulp_href)
        distribution = rpm_distribution_factory(publication=publication.pulp_href)
        downloaded_package = tmp_path / "package.rpm"
        downloaded_package.write_bytes(
            download_content_unit(
                distribution.base_path, get_package_repo_path(package.location_href)
            )
        )
        assert rpm_tool.verify_signature(downloaded_package)


def test_signed_repo_modify(
    tmp_path,
    delete_orphans_pre,
    monitor_task,
    download_content_unit,
    signing_gpg_metadata,
    rpm_package_signing_service,
    rpm_repository_factory,
    rpm_repository_api,
    rpm_package_factory,
    rpm_package_api,
    rpm_publication_factory,
    rpm_distribution_factory,
):
    """Ensure packages added via modify are signed before distribution."""

    _, fingerprint, _ = signing_gpg_metadata
    prefixed_fingerprint = f"v4:{fingerprint}"

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key.asc", KEY_V4_RSA4K.public_url))

    # Confirm the fixture RPM is initially unsigned.
    unsigned_package = tmp_path / RPM_PACKAGE_FILENAME
    unsigned_package.write_bytes(requests.get(RPM_UNSIGNED_URL).content)
    with pytest.raises(InvalidSignatureError, match="The package is not signed: .*"):
        rpm_tool.verify_signature(unsigned_package)

    repository = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=prefixed_fingerprint,
    )

    created_package = rpm_package_factory(url=RPM_UNSIGNED_URL)
    assert created_package.signing_keys is None
    package_href = created_package.pulp_href
    modify_response = rpm_repository_api.modify(
        repository.pulp_href, {"add_content_units": [package_href]}
    )
    task_result = monitor_task(modify_response.task)

    repository = rpm_repository_api.read(repository.pulp_href)
    signed_package = rpm_package_api.list(
        repository_version=repository.latest_version_href
    ).results[0]
    assert signed_package.pulp_href != created_package.pulp_href
    assert signed_package.signing_keys == [prefixed_fingerprint]
    assert signed_package.time_file != created_package.time_file
    assert sorted(task_result.created_resources) == sorted(
        [repository.latest_version_href, signed_package.pulp_href, signed_package.artifact]
    )

    publication = rpm_publication_factory(repository=repository.pulp_href)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)

    pkg_location_href = rpm_package_api.read(package_href).location_href
    downloaded_package = tmp_path / "modify-package.rpm"
    downloaded_package.write_bytes(
        download_content_unit(distribution.base_path, get_package_repo_path(pkg_location_href))
    )

    assert rpm_tool.verify_signature(downloaded_package)

    # attempt to add the package to the repository a second time (should produce same package href)
    modify_response = rpm_repository_api.modify(
        repository.pulp_href, {"add_content_units": [package_href]}
    )
    task_result = monitor_task(modify_response.task)

    repository = rpm_repository_api.read(repository.pulp_href)
    results = rpm_package_api.list(repository_version=repository.latest_version_href).results

    assert [signed_package.pulp_href] == [pkg.pulp_href for pkg in results]
    assert task_result.created_resources == []


def test_already_signed_package(
    delete_orphans_pre,
    monitor_task,
    signing_gpg_metadata,
    rpm_package_signing_service,
    rpm_repository_factory,
    rpm_repository_api,
    rpm_package_factory,
    rpm_package_api,
):
    """Don't sign a package if it's already signed with our key."""

    _, fingerprint, _ = signing_gpg_metadata
    prefixed_fingerprint = f"v4:{fingerprint}"

    repo_one = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=prefixed_fingerprint,
    )
    repo_two = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=prefixed_fingerprint,
    )

    created_package = rpm_package_factory(url=RPM_UNSIGNED_URL)
    package_href = created_package.pulp_href

    first_modify = rpm_repository_api.modify(
        repo_one.pulp_href,
        {"add_content_units": [package_href]},
    )
    task_result = monitor_task(first_modify.task)

    repo_one = rpm_repository_api.read(repo_one.pulp_href)
    repo_one_packages = rpm_package_api.list(
        repository_version=repo_one.latest_version_href
    ).results
    signed_package_href = repo_one_packages[0].pulp_href
    assert repo_one_packages[0].signing_keys == [prefixed_fingerprint]
    assert len(repo_one_packages) == 1
    assert sorted(task_result.created_resources) == sorted(
        [signed_package_href, repo_one_packages[0].artifact, repo_one.latest_version_href]
    )

    second_modify = rpm_repository_api.modify(
        repo_two.pulp_href,
        {"add_content_units": [signed_package_href]},
    )
    task_result = monitor_task(second_modify.task)

    repo_two = rpm_repository_api.read(repo_two.pulp_href)
    repo_two_packages = rpm_package_api.list(
        repository_version=repo_two.latest_version_href
    ).results
    assert len(repo_two_packages) == 1

    # The same signed package should be reused between repositories
    assert repo_two_packages[0].pulp_href == signed_package_href
    assert task_result.created_resources == [repo_two.latest_version_href]


def test_signing_with_primary_key_fingerprint(
    delete_orphans_pre,
    monitor_task,
    download_content_unit,
    signing_gpg_metadata,
    rpm_package_signing_service,
    rpm_repository_factory,
    rpm_repository_api,
    rpm_package_factory,
    rpm_package_api,
    rpm_publication_factory,
    rpm_distribution_factory,
    tmp_path,
):
    """Test that signing_keys is correct when package_signing_fingerprint is a primary key.

    When the signing key has a dedicated signing subkey, GnuPG signs with the subkey.
    signing_keys should reflect the actual signature fingerprints from the artifact.
    """
    gpg, signing_subkey_fpr, _ = signing_gpg_metadata
    primary_fpr = gpg.list_keys()[0]["fingerprint"]
    assert primary_fpr != signing_subkey_fpr, "Test requires a key with a separate signing subkey"

    prefixed_primary = f"v4:{primary_fpr}"
    prefixed_subkey = f"v4:{signing_subkey_fpr}"

    repository = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=prefixed_primary,
    )

    created_package = rpm_package_factory(url=RPM_UNSIGNED_URL)
    modify_response = rpm_repository_api.modify(
        repository.pulp_href, {"add_content_units": [created_package.pulp_href]}
    )
    monitor_task(modify_response.task)

    repository = rpm_repository_api.read(repository.pulp_href)
    signed_package = rpm_package_api.list(
        repository_version=repository.latest_version_href
    ).results[0]

    assert signed_package.pulp_href != created_package.pulp_href
    # GnuPG signs with the subkey even when the primary fingerprint is specified
    assert signed_package.signing_keys == [prefixed_subkey]

    # Verify the served package has a valid signature
    verifier = rpm_rs.Verifier()
    verifier.load_from_asc_bytes(requests.get(KEY_V4_RSA4K.public_url).content)

    publication = rpm_publication_factory(repository=repository.pulp_href)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)
    downloaded_package = tmp_path / "signed.rpm"
    downloaded_package.write_bytes(
        download_content_unit(
            distribution.base_path, get_package_repo_path(signed_package.location_href)
        )
    )
    pkg = rpm_rs.Package.open(str(downloaded_package))
    pkg.verify_signature(verifier)
    sig_fingerprints = [
        f"v4:{s.fingerprint.upper()}"
        for s in rpm_rs.PackageMetadata.open(str(downloaded_package)).signatures()
        if s.fingerprint
    ]
    assert signed_package.signing_keys == sig_fingerprints


def test_signed_repo_rejects_on_demand_content(
    init_and_sync,
    rpm_package_signing_service,
    signing_gpg_metadata,
    rpm_repository_factory,
    rpm_repository_api,
    rpm_package_api,
):
    """Ensure modify rejects on-demand content when signing is enabled."""
    source_repo, _ = init_and_sync(policy="on_demand")
    _, fingerprint, _ = signing_gpg_metadata
    destination_repo = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=f"v4:{fingerprint}",
    )

    packages = rpm_package_api.list(repository_version=source_repo.latest_version_href).results
    package_href = packages[0].pulp_href

    with pytest.raises(ApiException) as exc:
        rpm_repository_api.modify(
            destination_repo.pulp_href,
            {"add_content_units": [package_href]},
        )

    assert "Cannot add on-demand packages" in exc.value.body


@pytest.mark.parallel
def test_upload_signed_package(
    tmp_path,
    monitor_task,
    rpm_package_api,
    rpm_repository_factory,
):
    """Upload a pre-signed package without signing enabled; signing_keys should be populated."""
    repository = rpm_repository_factory()

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_SIGNED_URL).content)

    # Extract the expected fingerprint from the pre-signed RPM
    pkg = rpm_rs.PackageMetadata.open(str(file_to_upload))
    expected_sigs = [f"v4:{s.fingerprint.upper()}" for s in pkg.signatures() if s.fingerprint]
    assert len(expected_sigs) > 0

    upload_response = rpm_package_api.create(
        file=str(file_to_upload.absolute()),
        repository=repository.pulp_href,
    )
    package_href = monitor_task(upload_response.task).created_resources[1]
    package = rpm_package_api.read(package_href)

    assert package.signing_keys is not None
    assert package.signing_keys == expected_sigs


@pytest.mark.parallel
def test_upload_multi_signed_package(
    tmp_path,
    monitor_task,
    signing_gpg_extra,
    multi_signed_rpm,
    rpm_package_api,
    rpm_repository_factory,
):
    """Upload a package signed with multiple keys; signing_keys should contain all fingerprints."""
    key_a, key_b = signing_gpg_extra
    prefixed_a = f"v4:{key_a.signing_fingerprint.upper()}"
    prefixed_b = f"v4:{key_b.signing_fingerprint.upper()}"

    repository = rpm_repository_factory()

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    shutil.copy2(multi_signed_rpm, file_to_upload)

    upload_response = rpm_package_api.create(
        file=str(file_to_upload.absolute()),
        repository=repository.pulp_href,
    )
    package_href = monitor_task(upload_response.task).created_resources[1]
    package = rpm_package_api.read(package_href)

    assert package.signing_keys is not None
    assert len(package.signing_keys) == 2
    assert prefixed_a in package.signing_keys
    assert prefixed_b in package.signing_keys


@pytest.mark.parallel
def test_sign_already_signed_package_on_upload(
    tmp_path,
    monitor_task,
    download_content_unit,
    signing_gpg_extra,
    rpm_package_signing_service,
    rpm_package_api,
    rpm_repository_factory,
    rpm_publication_factory,
    rpm_distribution_factory,
):
    """Upload a pre-signed package to a signing-enabled repo with a different key.

    The resulting package should have signatures from both the original key and the new key.
    """
    _, key_b = signing_gpg_extra
    prefixed_b = f"v4:{key_b.signing_fingerprint.upper()}"

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_a.asc", KEY_V4_RSA2K.public_url))
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_b.asc", KEY_V4_RSA4K.public_url))

    # The fixture RPM is already signed with the old fixture key.
    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_SIGNED_URL).content)

    # Extract the existing signature fingerprint from the pre-signed RPM.
    pkg = rpm_rs.PackageMetadata.open(str(file_to_upload))
    existing_sigs = [f"v4:{s.fingerprint.upper()}" for s in pkg.signatures() if s.fingerprint]
    assert len(existing_sigs) > 0

    # Upload to a repo that signs with key_b.
    repository = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=prefixed_b,
    )
    upload_response = rpm_package_api.create(
        file=str(file_to_upload.absolute()),
        repository=repository.pulp_href,
    )
    package_href = monitor_task(upload_response.task).created_resources[2]
    package = rpm_package_api.read(package_href)

    assert package.signing_keys is not None
    assert len(package.signing_keys) == 2
    assert existing_sigs[0] in package.signing_keys
    assert prefixed_b in package.signing_keys

    # Verify the served package has valid signatures
    publication = rpm_publication_factory(repository=repository.pulp_href)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)
    downloaded_package = tmp_path / "package.rpm"
    downloaded_package.write_bytes(
        download_content_unit(distribution.base_path, get_package_repo_path(package.location_href))
    )
    assert rpm_tool.verify_signature(downloaded_package)


@pytest.mark.parallel
def test_sign_multi_signed_package_on_upload(
    tmp_path,
    monitor_task,
    download_content_unit,
    signing_gpg_extra,
    multi_signed_rpm,
    rpm_package_signing_service,
    rpm_package_api,
    rpm_repository_factory,
    rpm_publication_factory,
    rpm_distribution_factory,
):
    """Upload a multi-signed package to a signing-enabled repo with one of its existing keys.

    The package already has both signatures, so signing should be a no-op (the package is already
    signed with the requested key). The signing_keys should still contain both fingerprints.
    """
    key_a, key_b = signing_gpg_extra
    prefixed_a = f"v4:{key_a.signing_fingerprint.upper()}"
    prefixed_b = f"v4:{key_b.signing_fingerprint.upper()}"

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_a.asc", KEY_V4_RSA2K.public_url))
    rpm_tool.import_pubkey_file(get_fixture(tmp_path / "key_b.asc", KEY_V4_RSA4K.public_url))

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    shutil.copy2(multi_signed_rpm, file_to_upload)

    # Sign with key_a — which the package already has.
    repository = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href,
        package_signing_fingerprint=prefixed_a,
    )
    upload_response = rpm_package_api.create(
        file=str(file_to_upload.absolute()),
        repository=repository.pulp_href,
    )
    # When the package is already signed with the requested key, the signing task
    # should not create a new package — so the package href is at index 1.
    created_resources = monitor_task(upload_response.task).created_resources
    package_href = [r for r in created_resources if "/packages/" in r][0]
    package = rpm_package_api.read(package_href)

    assert package.signing_keys is not None
    assert len(package.signing_keys) == 2
    assert prefixed_a in package.signing_keys
    assert prefixed_b in package.signing_keys


@pytest.mark.parallel
def test_upload_mldsa_signed_package(
    tmp_path,
    monitor_task,
    rpm_package_api,
    rpm_repository_factory,
):
    """Upload a package signed with an ML-DSA (post-quantum) v6 key.

    The signing_keys field should contain the v6-prefixed fingerprint.
    """
    rpm_path = tmp_path / RPM_PACKAGE_FILENAME
    rpm_path.write_bytes(requests.get(RPM_UNSIGNED_URL).content)

    _sign_package(rpm_path, KEY_V6_MLDSA65_ED25519.private_url)

    pkg = rpm_rs.PackageMetadata.open(str(rpm_path))
    sigs = [s for s in pkg.signatures() if s.fingerprint is not None]
    assert len(sigs) == 1
    expected_fingerprint = f"v6:{sigs[0].fingerprint.upper()}"

    repository = rpm_repository_factory()

    upload_response = rpm_package_api.create(
        file=str(rpm_path.absolute()),
        repository=repository.pulp_href,
    )
    package_href = monitor_task(upload_response.task).created_resources[1]
    package = rpm_package_api.read(package_href)

    assert package.signing_keys is not None
    assert expected_fingerprint in package.signing_keys
