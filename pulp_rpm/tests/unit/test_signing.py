from types import SimpleNamespace

import subprocess

from pulp_rpm.app.tasks.signing import _verify_package_fingerprint


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
    assert _verify_package_fingerprint(package, "c6e7f081cf80e13146676e88829b606631645531")


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
    assert _verify_package_fingerprint(package, "999f7cbf38ab71f4")
