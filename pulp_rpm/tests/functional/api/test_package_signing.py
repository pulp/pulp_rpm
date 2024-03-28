import pytest
import requests
from pulpcore.client.pulp_rpm import RpmRpmPublication
from pulpcore.exceptions.validation import InvalidSignatureError

from pulp_rpm.app.shared_utils import RpmTool
from pulp_rpm.tests.functional.constants import (
    RPM_PACKAGE_FILENAME,
    RPM_UNSIGNED_URL,
)
from pulp_rpm.tests.functional.utils import get_package_repo_path


@pytest.mark.parallel
def test_register_rpm_package_signing_service(rpm_package_signing_service):
    """
    Register a sample rpmsign-based signing service and validate it works.
    """
    service = rpm_package_signing_service
    assert "/api/v3/signing-services/" in service.pulp_href


@pytest.mark.parallel
def test_sign_package_on_upload(
    tmp_path,
    pulpcore_bindings,
    monitor_task,
    gen_object_with_cleanup,
    download_content_unit,
    rpm_package_signing_service,
    rpm_package_api,
    rpm_repository_factory,
    rpm_publication_api,
    rpm_package_factory,
    rpm_distribution_factory,
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

    # Create Repository with related signing service
    repository = rpm_repository_factory(
        package_signing_service=rpm_package_signing_service.pulp_href
    )

    # Upload Package to Repository with signing-option on
    upload_attrs = {
        "file": str(file_to_upload.absolute()),
        "repository": repository.pulp_href,
        "sign_package": True,
    }
    upload_task_href = rpm_package_api.create(**upload_attrs).task
    package_href = monitor_task(upload_task_href).created_resources[2]
    package_loc_href = rpm_package_api.read(package_href).location_href

    # Verify that the final served package is signed
    publish_data = RpmRpmPublication(repository=repository.pulp_href)
    publication = gen_object_with_cleanup(rpm_publication_api, publish_data)
    distribution = rpm_distribution_factory(publication=publication.pulp_href)

    pkg_path = get_package_repo_path(package_loc_href)
    package_bytes = download_content_unit(distribution.base_path, pkg_path)
    downloaded_package = tmp_path / "package.rpm"
    downloaded_package.write_bytes(package_bytes)
    assert rpm_tool.verify_signature(downloaded_package)
