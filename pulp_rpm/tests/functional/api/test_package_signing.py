import subprocess

import pytest
import requests
from django.core.files.storage import default_storage
from rich import print

from pulp_rpm.app.models.content import RpmTool
from pulp_rpm.tests.functional.constants import (
    RPM_PACKAGE_FILENAME,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_UNSIGNED_URL,
)


@pytest.mark.parallel
def test_register_rpm_package_signing_service(rpm_package_signing_service):
    """
    Register a sample rpmsign-based signing service and validate it works.
    """
    service = rpm_package_signing_service
    assert "/api/v3/signing-services/" in service.pulp_href


@pytest.mark.parallel
def test_sign_package_on_upload(
    # rpm_package_factory, rpm_package_signing_service, pulpcore_bindings
    rpm_package_factory,
    rpm_package_signing_service,
    pulpcore_bindings,
    rpm_package_api,
    monitor_task,
    tmp_path,
):
    """Sign an Rpm Package on upload."""
    # Setup package to upload
    rpm_tool = RpmTool()
    file_to_upload = tmp_path / RPM_PACKAGE_FILENAME
    file_to_upload.write_bytes(requests.get(RPM_UNSIGNED_URL).content)

    # Upload package
    upload_attrs = {
        "file": str(file_to_upload.absolute()),
        # "sing-with": rpm_package_signing_service
    }
    upload_task = rpm_package_api.create(**upload_attrs).task
    package_href = monitor_task(upload_task).created_resources[0]
    package = rpm_package_api.read(package_href)

    # Get and Verify stored artifact
    artifact = pulpcore_bindings.ArtifactsApi.read(package.artifact)
    with default_storage.open(artifact.file, "r") as package_file:
        print(package_file, type(package_file))
        result = subprocess.run(["file", str(package_file)], capture_output=True).stdout
        print(result)
        assert package_file

    # artifacts = pulpcore_bindings.ArtifactsApi.list(fields=["file"]).results
    # for artifact in artifacts:
    #     with default_storage.open(artifact.file, "r") as package_file:
    #         print(package_file, type(package_file))
    #         result = subprocess.run(["file", str(package_file)], capture_output=True).stdout
    #         print(result)
    #         assert package_file
