import pytest


@pytest.mark.parallel
def test_add_rpm_package_signing_service(rpm_package_signing_service):
    service = rpm_package_signing_service
    assert "/api/v3/signing-services/" in service.pulp_href


def test_sign_package_with_rpm_package_signing_service():
    ...
