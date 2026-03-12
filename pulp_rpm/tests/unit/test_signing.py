import pytest
import requests
import rpm_rs

from pulp_rpm.app.tasks.signing import _verify_package_fingerprint
from pulp_rpm.tests.functional.constants import RPM_FIXTURE_SIGNED, RPM_FIXTURE_UNSIGNED


def _download_rpm(tmp_path, url, name="test.rpm"):
    path = str(tmp_path / name)
    data = requests.get(url).content
    with open(path, "wb") as f:
        f.write(data)
    return path


def _get_fingerprint(path):
    pkg = rpm_rs.PackageMetadata.open(path)
    return next(s.fingerprint for s in pkg.signatures() if s.fingerprint)


@pytest.fixture
def unsigned_rpm(tmp_path):
    return _download_rpm(tmp_path, RPM_FIXTURE_UNSIGNED)


@pytest.fixture
def signed_rpm(tmp_path):
    return _download_rpm(tmp_path, RPM_FIXTURE_SIGNED)


def test_verify_unsigned_package(unsigned_rpm):
    assert not _verify_package_fingerprint(unsigned_rpm, "v4:0000000000000000000000000000000000000000")


def test_verify_signed_package_matches(signed_rpm):
    fingerprint = _get_fingerprint(signed_rpm)
    assert _verify_package_fingerprint(signed_rpm, f"v4:{fingerprint.upper()}")


def test_verify_signed_package_case_insensitive(signed_rpm):
    fingerprint = _get_fingerprint(signed_rpm)
    assert _verify_package_fingerprint(signed_rpm, f"v4:{fingerprint.lower()}")
    assert _verify_package_fingerprint(signed_rpm, f"v4:{fingerprint.upper()}")


def test_verify_signed_package_wrong_fingerprint(signed_rpm):
    assert not _verify_package_fingerprint(signed_rpm, "v4:0000000000000000000000000000000000000000")


def test_verify_fingerprint_without_prefix(signed_rpm):
    fingerprint = _get_fingerprint(signed_rpm)
    assert _verify_package_fingerprint(signed_rpm, fingerprint.upper())
