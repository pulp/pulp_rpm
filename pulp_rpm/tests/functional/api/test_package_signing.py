import pytest
import requests
from django.core.files.storage import default_storage
from pulpcore.exceptions.validation import InvalidSignatureError

from pulp_rpm.app.shared_utils import RpmTool
from pulp_rpm.tests.functional.constants import RPM_PACKAGE_FILENAME, RPM_UNSIGNED_URL


@pytest.mark.parallel
def test_register_rpm_package_signing_service(rpm_package_signing_service):
    """
    Register a sample rpmsign-based signing service and validate it works.
    """
    service = rpm_package_signing_service
    assert "/api/v3/signing-services/" in service.pulp_href


@pytest.mark.parallel
def test_sign_package_on_upload(
    rpm_package_factory,
    rpm_repository_factory,
    rpm_package_signing_service,
    pulpcore_bindings,
    rpm_package_api,
    monitor_task,
    tmp_path,
):
    """Sign an Rpm Package with the Package Upload endpoint."""
    # Setup rpm package file to upload
    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_string(rpm_package_signing_service.public_key)
    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_UNSIGNED_URL).content)

    # Assure it is not signed
    with pytest.raises(InvalidSignatureError, match="The package is not signed: .*"):
        rpm_tool.verify_signature(file_to_upload)

    # Create Repository with signing service
    repository = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href
    )

    # Upload Package to Repository with signing-option on
    upload_attrs = {
        "file": str(file_to_upload.absolute()),
        "repository": repository.pulp_href,
        "sign_package": True,
    }
    upload_task = rpm_package_api.create(**upload_attrs).task
    # created_resources: [0] artifact [1] repository_version [2] package
    package_href = monitor_task(upload_task).created_resources[2]
    package = rpm_package_api.read(package_href)

    # Verify stored artifact is properly signed
    artifact = pulpcore_bindings.ArtifactsApi.read(package.artifact)
    with default_storage.open(artifact.file, "rb") as package_file:
        package_file.read()  # hopefully will trigger download on external storages
        assert rpm_tool.verify_signature(package_file.name)
