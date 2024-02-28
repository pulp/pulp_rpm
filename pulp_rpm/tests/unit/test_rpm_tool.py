import pytest
from pulpcore.plugin.exceptions import InvalidSignatureError

from pulp_rpm.app.shared_utils import RpmTool


def test_get_empty_rpm_is_valid(tmp_path):
    """Can get a valid rpm."""
    rpm_pkg = RpmTool.get_empty_rpm(tmp_path)
    assert rpm_pkg.exists()
    with open(rpm_pkg, "rb") as pkg:
        # https://rpm-software-management.github.io/rpm/manual/format_lead.html
        rpm_magic_numbers = bytes([0xED, 0xAB, 0xEE, 0xDB])
        pkg_lead = pkg.read(96)
        rpm_major_version = pkg_lead[4]
        assert pkg_lead[:4] == rpm_magic_numbers
        assert rpm_major_version == 3


@pytest.mark.skip
def test_alternative_root_works(tpm_path):
    """Can use alternative "rpm --root" option for isolated operations."""
    ...


@pytest.mark.skip
def test_import_pubkey_and_verify_signature_when_valid(tmp_path):
    """Can import pubkeys to internal db and verify a package with it."""
    pubkey_file = ...
    rpm_pkg_file = ...
    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(pubkey_file)
    rpm_tool.verify_signature(rpm_pkg_file)


@pytest.mark.skip
def test_verify_signature_when_unsigned(tmp_path):
    """Can verify that a package is unsigned"""
    pubkey_file = ...
    rpm_pkg_file = ...
    rpm_tool = RpmTool(tmp_path)
    rpm_tool.import_pubkey_file(pubkey_file)
    with pytest.raises(InvalidSignatureError, match=""):
        rpm_tool.verify_signature(rpm_pkg_file)


@pytest.mark.skip
def test_verify_signature_when_invalid(tmp_path):
    """Can verify that a package's signature is invalid.
    That means that no pubkeys in the rpm db can validate the package.
    """
    rpm_pkg_file = ...
    rpm_tool = RpmTool(tmp_path)
    with pytest.raises(InvalidSignatureError, match=""):
        rpm_tool.verify_signature(rpm_pkg_file)
