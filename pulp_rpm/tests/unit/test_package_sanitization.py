"""Tests for sanitizing malformed RPM changelog metadata during package conversion."""

import createrepo_c as cr
import pytest
from rpm_rs import PackageBuilder

from pulp_rpm.app.models import Package


def _createrepo_package_with_changelog(tmp_path, name, replacements):
    """Build a malformed-changelog RPM and load it with createrepo_c."""
    builder = PackageBuilder(name, "1.0", "MIT", "noarch")
    builder.add_changelog_entry("AuthorXYName", "DescriptionABCDE", 1_700_000_000)
    rpm_bytes = builder.build().to_bytes()

    for original, replacement in replacements:
        assert len(original) == len(replacement)
        assert rpm_bytes.count(original) == 1
        rpm_bytes = rpm_bytes.replace(original, replacement, 1)

    path = tmp_path / f"{name}-1.0-1.noarch.rpm"
    path.write_bytes(rpm_bytes)
    return cr.package_from_rpm(str(path))


@pytest.mark.skip("Needs createrepo_c 1.2.6")
def test_createrepo_to_dict_replaces_xml_forbidden_changelog_characters(tmp_path):
    """Replaces XML-forbidden characters in changelogs loaded from an RPM header."""
    package = _createrepo_package_with_changelog(
        tmp_path,
        "changelog-control-chars",
        [
            (b"AuthorXYName", b"Author\x1b\tName"),
            (b"DescriptionABCDE", b"Description\x1f\n\xef\xbf\xbe"),
        ],
    )

    package_dict = Package.createrepo_to_dict(package)

    assert package_dict["changelogs"] == [("Author�\tName", 1_700_000_000, "Description�\n�")]


def test_createrepo_to_dict_lossy_decodes_non_utf8_changelog_characters(tmp_path):
    """Parses non-UTF-8 changelogs when RPMTAG_ENCODING does not claim UTF-8."""
    package = _createrepo_package_with_changelog(
        tmp_path,
        "invalid-utf8-changelog",
        [
            # if the header contains RPMTAG_ENCODING="utf-8", rpm-rs will fail outright if
            # non-utf-8 text is found, so overwrite that value to fall back to replacement behavior
            (b"utf-8\x00", b"ascii\x00"),
            (b"AuthorXYName", b"Author\xffYName"),
            (b"DescriptionABCDE", b"Description\xffBCDE"),
        ],
    )

    package_dict = Package.createrepo_to_dict(package)

    assert package_dict["changelogs"] == [("Author�YName", 1_700_000_000, "Description�BCDE")]
