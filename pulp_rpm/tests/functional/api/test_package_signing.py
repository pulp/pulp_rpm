from dataclasses import dataclass
import hashlib
from pathlib import Path
import uuid

import pytest
import requests
from pulpcore.exceptions.validation import InvalidSignatureError

from pulp_rpm.app.shared_utils import RpmTool
from pulp_rpm.tests.functional.constants import RPM_PACKAGE_FILENAME, RPM_UNSIGNED_URL
from pulp_rpm.tests.functional.utils import get_package_repo_path


def get_fixture(path: Path, url: str) -> Path:
    path.write_bytes(requests.get(url).content)
    return path


@pytest.mark.parallel
def test_register_rpm_package_signing_service(rpm_package_signing_service):
    """
    Register a sample rpmsign-based signing service and validate it works.
    """
    service = rpm_package_signing_service
    assert "/api/v3/signing-services/" in service.pulp_href


@dataclass
class GPGMetadata:
    pubkey: str
    fingerprint: str
    keyid: str


@pytest.fixture
def signing_gpg_extra(signing_gpg_metadata):
    """GPG instance with an extra gpg keypair registered."""
    PRIVATE_KEY_PULP_QE = (
        "https://raw.githubusercontent.com/pulp/pulp-fixtures/master/common/GPG-PRIVATE-KEY-pulp-qe"
    )
    gpg, fingerprint_a, keyid_a = signing_gpg_metadata

    response_private = requests.get(PRIVATE_KEY_PULP_QE)
    response_private.raise_for_status()
    import_result = gpg.import_keys(response_private.content)
    fingerprint_b = import_result.fingerprints[0]
    gpg.trust_keys(fingerprint_b, "TRUST_ULTIMATE")

    pubkey_a = gpg.export_keys(fingerprint_a)
    pubkey_b = gpg.export_keys(fingerprint_b)
    return (
        GPGMetadata(pubkey_a, fingerprint_a, fingerprint_a[-8:]),
        GPGMetadata(pubkey_b, fingerprint_b, fingerprint_b[-8:]),
    )


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
    rpm_repository_factory,
    rpm_publication_factory,
    rpm_package_factory,
    rpm_distribution_factory,
):
    """
    Sign an Rpm Package with the Package Upload endpoint.

    This ensures different
    """
    # Setup RPM tool and package to upload
    gpg_a, gpg_b = signing_gpg_extra
    fingerprint_set = set([gpg_a.fingerprint, gpg_b.fingerprint])
    assert len(fingerprint_set) == 2

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_string(gpg_a.pubkey)
    rpm_tool.import_pubkey_string(gpg_b.pubkey)

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_UNSIGNED_URL).content)
    with pytest.raises(InvalidSignatureError, match="The package is not signed: .*"):
        rpm_tool.verify_signature(file_to_upload)

    # Upload Package to Repository
    # The same file is uploaded, but signed with different keys each time
    for fingerprint in fingerprint_set:
        repository = rpm_repository_factory(
            package_signing_service=rpm_package_signing_service.pulp_href,
            package_signing_fingerprint=fingerprint,
        )
        upload_response = rpm_package_api.create(
            file=str(file_to_upload.absolute()),
            repository=repository.pulp_href,
        )
        package_href = monitor_task(upload_response.task).created_resources[2]
        pkg_location_href = rpm_package_api.read(package_href).location_href

        # Verify that the final served package is signed
        publication = rpm_publication_factory(repository=repository.pulp_href)
        distribution = rpm_distribution_factory(publication=publication.pulp_href)
        downloaded_package = tmp_path / "package.rpm"
        downloaded_package.write_bytes(
            download_content_unit(distribution.base_path, get_package_repo_path(pkg_location_href))
        )
        assert rpm_tool.verify_signature(downloaded_package)


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
    Sign an Rpm Package with the Package Upload endpoint.

    This ensures different
    """
    # Setup RPM tool and package to upload
    gpg_a, gpg_b = signing_gpg_extra
    fingerprint_set = set([gpg_a.fingerprint, gpg_b.fingerprint])
    assert len(fingerprint_set) == 2

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_string(gpg_a.pubkey)
    rpm_tool.import_pubkey_string(gpg_b.pubkey)

    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_UNSIGNED_URL).content)
    with pytest.raises(InvalidSignatureError, match="The package is not signed: .*"):
        rpm_tool.verify_signature(file_to_upload)

    # Upload Package to Repository
    # The same file is uploaded, but signed with different keys each time
    for fingerprint in fingerprint_set:
        repository = rpm_repository_factory(
            package_signing_service=rpm_package_signing_service.pulp_href,
            package_signing_fingerprint=fingerprint,
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
        pkg_location_href = rpm_package_api.read(package_href).location_href

        # Verify that the final served package is signed
        publication = rpm_publication_factory(repository=repository.pulp_href)
        distribution = rpm_distribution_factory(publication=publication.pulp_href)
        downloaded_package = tmp_path / "package.rpm"
        downloaded_package.write_bytes(
            download_content_unit(distribution.base_path, get_package_repo_path(pkg_location_href))
        )
        assert rpm_tool.verify_signature(downloaded_package)
