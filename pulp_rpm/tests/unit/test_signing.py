from types import SimpleNamespace

import pytest
import requests
import rpm_rs

from pulp_rpm.app.shared_utils import extract_signing_keys, format_signing_keys
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


def _mock_sig(version=rpm_rs.SignatureVersion.V4, fingerprint=None, key_id=None):
    return SimpleNamespace(version=version, fingerprint=fingerprint, key_id=key_id)


@pytest.fixture
def unsigned_rpm(tmp_path):
    return _download_rpm(tmp_path, RPM_FIXTURE_UNSIGNED)


@pytest.fixture
def signed_rpm(tmp_path):
    return _download_rpm(tmp_path, RPM_FIXTURE_SIGNED)


def test_verify_unsigned_package(unsigned_rpm):
    assert not _verify_package_fingerprint(
        unsigned_rpm, "v4:0000000000000000000000000000000000000000"
    )


def test_verify_signed_package_matches(signed_rpm):
    fingerprint = _get_fingerprint(signed_rpm)
    assert _verify_package_fingerprint(signed_rpm, f"v4:{fingerprint.upper()}")


def test_verify_signed_package_case_insensitive(signed_rpm):
    fingerprint = _get_fingerprint(signed_rpm)
    assert _verify_package_fingerprint(signed_rpm, f"v4:{fingerprint.lower()}")
    assert _verify_package_fingerprint(signed_rpm, f"v4:{fingerprint.upper()}")


def test_verify_signed_package_wrong_fingerprint(signed_rpm):
    assert not _verify_package_fingerprint(
        signed_rpm, "v4:0000000000000000000000000000000000000000"
    )


def test_verify_fingerprint_without_prefix(signed_rpm):
    fingerprint = _get_fingerprint(signed_rpm)
    assert _verify_package_fingerprint(signed_rpm, fingerprint.upper())


# Tests for format_signing_keys


def test_format_signing_keys_with_fingerprint():
    sigs = [_mock_sig(fingerprint="abcd1234", key_id="1234")]
    result = format_signing_keys(sigs)
    assert result == ["v4:ABCD1234"]


def test_format_signing_keys_with_key_id_only():
    """Signatures with only key_id (no fingerprint) should use 'keyid:' prefix."""
    sigs = [_mock_sig(fingerprint=None, key_id="ee4d7792f748182b")]
    result = format_signing_keys(sigs)
    assert result == ["keyid:EE4D7792F748182B"]


def test_format_signing_keys_prefers_fingerprint_over_key_id():
    sigs = [_mock_sig(fingerprint="abcd1234abcd1234", key_id="abcd1234")]
    result = format_signing_keys(sigs)
    assert result == ["v4:ABCD1234ABCD1234"]


def test_format_signing_keys_mixed():
    """Mix of signatures with fingerprint and key_id-only."""
    sigs = [
        _mock_sig(fingerprint="aaaa1111", key_id="1111"),
        _mock_sig(fingerprint=None, key_id="bbbb2222"),
    ]
    result = format_signing_keys(sigs)
    assert len(result) == 2
    assert "v4:AAAA1111" in result
    assert "keyid:BBBB2222" in result


def test_format_signing_keys_no_fingerprint_no_key_id():
    """Signatures with neither fingerprint nor key_id should be excluded."""
    sigs = [_mock_sig(fingerprint=None, key_id=None)]
    result = format_signing_keys(sigs)
    assert result == []


def test_format_signing_keys_empty():
    assert format_signing_keys([]) == []


def test_format_signing_keys_v6():
    sigs = [_mock_sig(version=rpm_rs.SignatureVersion.V6, fingerprint="abcd1234")]
    result = format_signing_keys(sigs)
    assert result == ["v6:ABCD1234"]


# Tests for extract_signing_keys


def test_extract_signing_keys_signed_rpm(signed_rpm):
    keys = extract_signing_keys(signed_rpm)
    assert len(keys) > 0
    assert all(k.startswith("v4:") or k.startswith("v6:") for k in keys)


def test_extract_signing_keys_unsigned_rpm(unsigned_rpm):
    keys = extract_signing_keys(unsigned_rpm)
    assert keys == []
