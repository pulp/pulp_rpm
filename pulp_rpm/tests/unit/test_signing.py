from types import SimpleNamespace

import pytest
import subprocess

from pulp_rpm.app.shared_utils import (
    SIGNING_FINGERPRINT_RE,
    normalize_signing_fingerprint,
    parse_signing_fingerprint,
)
from pulp_rpm.app.tasks.signing import _verify_package_fingerprint


@pytest.mark.parametrize(
    "value",
    [
        "v3:0123456789ABCDEF0123456789ABCDEF",
        "v4:0123456789ABCDEF0123456789ABCDEF01234567",
        "v5:" + "A" * 64,
        "v6:" + "B" * 64,
        "keyid:0123456789ABCDEF",
    ],
)
def test_signing_fingerprint_re_valid(value):
    assert SIGNING_FINGERPRINT_RE.match(value)


@pytest.mark.parametrize(
    "value",
    [
        "0123456789ABCDEF0123456789ABCDEF01234567",  # no prefix
        "v4:ghijkl",  # non-hex
        "v4:0123",  # too short
        "keyid:0123",  # too short
        "keyid:0123456789ABCDEF0",  # too long
        "v4:abcdef1234567890abcdef1234567890abcdef12",  # lowercase
    ],
)
def test_signing_fingerprint_re_invalid(value):
    assert not SIGNING_FINGERPRINT_RE.match(value)


def test_normalize_signing_fingerprint():
    assert (
        normalize_signing_fingerprint("v4:abcdef1234567890abcdef1234567890abcdef12")
        == "v4:ABCDEF1234567890ABCDEF1234567890ABCDEF12"
    )
    assert normalize_signing_fingerprint("keyid:abcdef1234567890") == "keyid:ABCDEF1234567890"


def test_parse_signing_fingerprint():
    assert parse_signing_fingerprint("v4:ABCDEF12") == "ABCDEF12"
    assert parse_signing_fingerprint("keyid:0123456789ABCDEF") == "0123456789ABCDEF"


def test_verify_package_fingerprint_accepts_rpm_fingerprint(monkeypatch, tmp_path):
    rpm_output = """\
    Header OpenPGP V4 signature, key fingerprint: c6e7f081cf80e13146676e88829b606631645531: OK
    Header SHA256 digest: OK
    Payload SHA256 digest: OK
    """
    fake_result = SimpleNamespace(stdout=rpm_output, stderr="")

    def fake_run(*args, **kwargs):
        return fake_result

    monkeypatch.setattr(subprocess, "run", fake_run)
    package = SimpleNamespace(name=str(tmp_path / "example.rpm"))
    assert _verify_package_fingerprint(package, "v4:C6E7F081CF80E13146676E88829B606631645531")


def test_verify_package_fingerprint_accepts_long_key_id(monkeypatch, tmp_path):
    rpm_output = """\
    Header OpenPGP V4 RSA/SHA256 signature, key ID 999f7cbf38ab71f4: NOKEY
    Header SHA256 digest: OK
    Payload SHA256 digest: OK
    Legacy OpenPGP V4 RSA/SHA256 signature, key ID 999f7cbf38ab71f4: NOKEY
    """
    fake_result = SimpleNamespace(stdout=rpm_output, stderr="")

    def fake_run(*args, **kwargs):
        return fake_result

    monkeypatch.setattr(subprocess, "run", fake_run)
    package = SimpleNamespace(name=str(tmp_path / "example.rpm"))
    assert _verify_package_fingerprint(package, "keyid:999F7CBF38AB71F4")
