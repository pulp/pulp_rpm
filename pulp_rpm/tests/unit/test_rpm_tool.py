import socket
from pathlib import Path

import pytest
import requests
from pulpcore.plugin.exceptions import InvalidSignatureError

from pulp_rpm.app.shared_utils import RpmTool
from pulp_rpm.tests.functional.constants import PUBLIC_GPG_KEY_URL, RPM_SIGNED_URL, RPM_UNSIGNED_URL


def connection_guard(*args, **kwargs):
    raise Exception("I told you not to use the Internet!")


def get_fixture(tmp_path: Path, url: str):
    """Utility to get unsigned package"""
    result = requests.get(url)
    file = tmp_path / result.url.split("/")[-1]
    file.write_bytes(result.content)
    return file


def test_can_get_empty_rpm(tmp_path, monkeypatch):
    """
    Can get a valid rpm without hitting the internet.

    This rpm can be used in production by the SigningService.validate() method, which
    is used to validate a provided signing script knows how to sign an rpm blob.
    """
    # Should't hit the internet
    # https://stackoverflow.com/a/18601897
    monkeypatch.setattr(socket, "socket", connection_guard)
    rpm_pkg = RpmTool.get_empty_rpm(tmp_path)
    assert rpm_pkg.exists()


def test_verify_signature_is_valid(tmp_path):
    """Can verify that a package is unsigned"""
    pkg_file = get_fixture(tmp_path, RPM_SIGNED_URL)
    pubkey = get_fixture(tmp_path, PUBLIC_GPG_KEY_URL)

    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(pubkey)
    rpm_tool.verify_signature(pkg_file)


def test_verify_package_is_unsigned(tmp_path):
    """Can verify that a package is unsigned"""
    pkg_file = get_fixture(tmp_path, RPM_UNSIGNED_URL)

    rpm_tool = RpmTool(tmp_path)
    with pytest.raises(InvalidSignatureError, match=RpmTool.UNSIGNED_ERROR_MSG):
        rpm_tool.verify_signature(pkg_file)


def test_verify_signature_is_invalid(tmp_path):
    """Can verify that a package's signature is invalid.
    That means that no pubkeys in the rpm db can validate the package.
    """
    pkg_file = get_fixture(tmp_path, RPM_SIGNED_URL)

    rpm_tool = RpmTool(tmp_path)
    with pytest.raises(InvalidSignatureError, match=RpmTool.INVALID_SIGNATURE_ERROR_MSG):
        rpm_tool.verify_signature(pkg_file)


def test_alternative_root_works(tmp_path):
    """Can use alternative "rpm --root" option for isolated operations."""
    pkg_file = get_fixture(tmp_path, RPM_SIGNED_URL)
    pubkey = get_fixture(tmp_path, PUBLIC_GPG_KEY_URL)

    # 1. First instance imports pubkey using a custom root
    root_1 = tmp_path / "root_1"
    rpm_tool_1 = RpmTool(root=root_1)
    rpm_tool_1.import_pubkey_file(str(pubkey))
    rpm_tool_1.verify_signature(pkg_file)

    # 2. Second instance uses a different root:
    # Because it doesnt have access to the other db (in root_1),
    # it raises for not being able to find the pubkey to verify the pkg
    root_2 = tmp_path / "root_2"
    rpm_tool_2 = RpmTool(root=root_2)
    with pytest.raises(InvalidSignatureError, match=RpmTool.INVALID_SIGNATURE_ERROR_MSG):
        rpm_tool_2.verify_signature(pkg_file)
