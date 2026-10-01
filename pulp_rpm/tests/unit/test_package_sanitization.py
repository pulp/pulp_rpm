"""Tests for sanitizing malformed RPM changelog metadata during package conversion."""

import rpmrepo_metadata as rpmmd
from rpm_rs import PackageBuilder

from pulp_rpm.app.models import Package


def _rpmrepo_package_with_changelog(tmp_path, name, replacements):
    """Build a malformed-changelog RPM and load it with rpmrepo_metadata."""
    builder = PackageBuilder(name, "1.0", "MIT", "noarch")
    builder.add_changelog_entry("AuthorXYName", "DescriptionABCDE", 1_700_000_000)
    rpm_bytes = builder.build().to_bytes()

    for original, replacement in replacements:
        assert len(original) == len(replacement)
        assert rpm_bytes.count(original) == 1
        rpm_bytes = rpm_bytes.replace(original, replacement, 1)

    path = tmp_path / f"{name}-1.0-1.noarch.rpm"
    path.write_bytes(rpm_bytes)
    return rpmmd.Package.from_file(path)


def test_rpmrepo_to_dict_strips_xml_forbidden_changelog_characters(tmp_path):
    """Strips XML-forbidden characters from changelogs loaded from an RPM header."""
    package = _rpmrepo_package_with_changelog(
        tmp_path,
        "changelog-control-chars",
        [
            (b"AuthorXYName", b"Author\x1b\tName"),
            (b"DescriptionABCDE", b"Description\x1f\n\xef\xbf\xbe"),
        ],
    )

    package_dict = Package.rpmrepo_to_dict(package)

    assert package_dict["changelogs"] == [("Author\tName", 1_700_000_000, "Description\n")]


def test_rpmrepo_to_dict_lossy_decodes_non_utf8_changelog_characters(tmp_path):
    """Parses non-UTF-8 changelogs when RPMTAG_ENCODING does not claim UTF-8."""
    package = _rpmrepo_package_with_changelog(
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

    package_dict = Package.rpmrepo_to_dict(package)

    assert package_dict["changelogs"] == [("Author�YName", 1_700_000_000, "Description�BCDE")]
