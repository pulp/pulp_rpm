from types import SimpleNamespace

import pytest
import requests
import rpm_rs

from pulp_rpm.app.shared_utils import extract_signing_keys, format_signing_keys, signing_key_matches
from pulp_rpm.app.tasks.signing import _verify_package_fingerprint
from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_KEYID_SIGNED,
    RPM_FIXTURE_SIGNED,
    RPM_FIXTURE_UNSIGNED,
)

V4_FINGERPRINT = "AA86F75E427A19DD33346403EE4D7792F748182B"
V4_KEY_ID = "EE4D7792F748182B"  # low-order 64 bits of V4_FINGERPRINT
V6_FINGERPRINT = "CB186C4F0609A697D5A3BCE4DB0E5CD9E4B3394501AB1650B7FE1AAD1C1AFB4C"
V6_KEY_ID = "CB186C4F0609A697"  # high-order 64 bits of V6_FINGERPRINT


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


@pytest.fixture
def key_id_only_rpm(tmp_path):
    """An RPM signed by the same key as signed_rpm, but with no issuer fingerprint.

    Signed by a GnuPG predating the issuer fingerprint subpacket, as packages in
    the wild often are.
    """
    return _download_rpm(tmp_path, RPM_FIXTURE_KEYID_SIGNED, name="key-id-only.rpm")


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


def test_verify_key_id_against_signed_package(signed_rpm):
    """A repo configured with a 'keyid:' fingerprint matches a full package signature."""
    # signed_rpm has a v4 signature, whose key ID is the low-order 64 bits of the fingerprint.
    fingerprint = _get_fingerprint(signed_rpm).upper()
    assert _verify_package_fingerprint(signed_rpm, f"keyid:{fingerprint[-16:]}")
    assert not _verify_package_fingerprint(signed_rpm, f"keyid:{fingerprint[:16]}")


def test_verify_key_id_only_signature_matches_full_fingerprint(signed_rpm, key_id_only_rpm):
    """A package signature carrying only an issuer key ID matches a configured fingerprint."""
    fingerprint = _get_fingerprint(signed_rpm).upper()

    assert extract_signing_keys(key_id_only_rpm) == [f"keyid:{fingerprint[-16:]}"]
    assert _verify_package_fingerprint(key_id_only_rpm, f"v4:{fingerprint}")


# Tests for signing_key_matches


def test_signing_key_matches_no_signing_keys():
    assert not signing_key_matches(f"v4:{V4_FINGERPRINT}", [])


def test_signing_key_matches_identical_fingerprint():
    assert signing_key_matches(f"v4:{V4_FINGERPRINT}", [f"v4:{V4_FINGERPRINT}"])


def test_signing_key_matches_is_case_insensitive():
    assert signing_key_matches(f"v4:{V4_FINGERPRINT.lower()}", [f"v4:{V4_FINGERPRINT.upper()}"])


def test_signing_key_matches_bare_fingerprint_assumed_v4():
    assert signing_key_matches(V4_FINGERPRINT, [f"v4:{V4_FINGERPRINT}"])
    assert signing_key_matches(V4_FINGERPRINT, [f"keyid:{V4_KEY_ID}"])


def test_signing_key_matches_different_fingerprint():
    assert not signing_key_matches(f"v4:{V4_FINGERPRINT}", ["v4:" + "0" * 40])


def test_signing_key_matches_v4_fingerprint_against_key_id():
    """A v4 key ID is the low-order 64 bits of its fingerprint."""
    assert signing_key_matches(f"v4:{V4_FINGERPRINT}", [f"keyid:{V4_KEY_ID}"])
    assert not signing_key_matches(f"v4:{V4_FINGERPRINT}", [f"keyid:{V4_FINGERPRINT[:16]}"])


def test_signing_key_matches_key_id_against_v4_fingerprint():
    """The comparison is symmetric: a configured key ID matches a full fingerprint."""
    assert signing_key_matches(f"keyid:{V4_KEY_ID}", [f"v4:{V4_FINGERPRINT}"])
    assert not signing_key_matches(f"keyid:{V4_FINGERPRINT[:16]}", [f"v4:{V4_FINGERPRINT}"])


def test_signing_key_matches_v6_fingerprint_against_key_id():
    """A v6 key ID is the high-order 64 bits of its fingerprint, not the low-order ones."""
    assert signing_key_matches(f"v6:{V6_FINGERPRINT}", [f"keyid:{V6_KEY_ID}"])
    assert not signing_key_matches(f"v6:{V6_FINGERPRINT}", [f"keyid:{V6_FINGERPRINT[-16:]}"])


def test_signing_key_matches_key_id_against_v6_fingerprint():
    assert signing_key_matches(f"keyid:{V6_KEY_ID}", [f"v6:{V6_FINGERPRINT}"])
    assert not signing_key_matches(f"keyid:{V6_FINGERPRINT[-16:]}", [f"v6:{V6_FINGERPRINT}"])


def test_signing_key_matches_identical_key_ids():
    assert signing_key_matches(f"keyid:{V4_KEY_ID}", [f"keyid:{V4_KEY_ID}"])
    assert not signing_key_matches(f"keyid:{V4_KEY_ID}", [f"keyid:{V6_KEY_ID}"])


def test_signing_key_matches_requires_same_version():
    """Fingerprints of different versions are different keys even if the hex matches."""
    assert not signing_key_matches(f"v4:{V4_FINGERPRINT}", [f"v6:{V4_FINGERPRINT}"])


def test_signing_key_matches_ignores_truncated_key_ids():
    """Short key IDs are too collision-prone to match on, unlike a full 16-hex key ID."""
    assert not signing_key_matches(f"v4:{V4_FINGERPRINT}", [f"keyid:{V4_KEY_ID[-8:]}"])
    assert not signing_key_matches(f"keyid:{V4_KEY_ID[-8:]}", [f"v4:{V4_FINGERPRINT}"])


def test_signing_key_matches_any_of_multiple_signing_keys():
    signing_keys = ["v4:" + "0" * 40, f"keyid:{V4_KEY_ID}"]
    assert signing_key_matches(f"v4:{V4_FINGERPRINT}", signing_keys)


def test_signing_key_matches_unknown_version_prefix():
    """An unknown version has no known key ID rule, so only exact equality can match."""
    assert signing_key_matches(f"v5:{V4_FINGERPRINT}", [f"v5:{V4_FINGERPRINT}"])
    assert not signing_key_matches(f"v5:{V4_FINGERPRINT}", [f"keyid:{V4_KEY_ID}"])


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
