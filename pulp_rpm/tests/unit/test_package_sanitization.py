"""Tests for sanitizing malformed RPM changelog metadata during package conversion."""

import xml.etree.ElementTree as ET

import createrepo_c as cr
import pytest
from rpm_rs import PackageBuilder

from pulpcore.plugin.models import Domain

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


def test_createrepo_to_dict_replaces_xml_forbidden_changelog_control_characters(tmp_path):
    """Replaces XML-forbidden control characters in changelogs loaded from an RPM header."""
    package = _createrepo_package_with_changelog(
        tmp_path,
        "changelog-control-chars",
        [
            (b"AuthorXYName", b"Author\x1b\tName"),
            (b"DescriptionABCDE", b"Description\x1f\n\x01\x02\x03"),
        ],
    )

    package_dict = Package.createrepo_to_dict(package)

    assert package_dict["changelogs"] == [("Author�\tName", 1_700_000_000, "Description�\n���")]


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


def _create_unsanitary_package(**overrides):
    """Create and reload a package with control characters in the database metadata."""
    domain, _ = Domain.objects.get_or_create(name="default")
    package_data = {
        "name": "legacy-metadata",
        "epoch": "0",
        "version": "1.0",
        "release": "1",
        "arch": "noarch",
        "pkgId": "0" * 64,
        "checksum_type": "sha256",
        "summary": "\x08summary",
        "description": "\x08description",
        "url": "https://example.invalid/\x08package",
        "changelogs": [["\x08author", 1_700_000_000, "\x08changelog"]],
        "location_base": "",
        "location_href": "legacy-metadata-1.0-1.noarch.rpm",
        "rpm_buildhost": "\x08buildhost",
        "rpm_group": "\x08group",
        "rpm_license": "\x08license",
        "rpm_packager": "\x08packager",
        "rpm_sourcerpm": "",
        "rpm_vendor": "\x08vendor",
        "rpm_header_start": 0,
        "rpm_header_end": 0,
        "size_archive": 0,
        "size_installed": 0,
        "size_package": 0,
        "time_build": 0,
        "time_file": 0,
        "_pulp_domain": domain,
    }
    package_data.update(overrides)
    package = Package.objects.create(**package_data)
    package.refresh_from_db()
    return package


@pytest.mark.django_db
def test_createrepo_writer_replaces_forbidden_display_chars(tmp_path):
    """Publishes metadata with XML-forbidden characters replaced when such transformations are possible."""
    package = _create_unsanitary_package()

    with cr.RepositoryWriter(str(tmp_path), compression=cr.NO_COMPRESSION) as writer:
        writer.set_num_of_pkgs(1)
        writer.add_pkg(package.to_createrepo_c())

    repodata = tmp_path / "repodata"
    for metadata in (next(repodata.glob("*-primary.xml")), next(repodata.glob("*-other.xml"))):
        text = metadata.read_text()
        ET.fromstring(text)
        assert "\x08" not in text
        assert "�" in text


@pytest.mark.django_db
@pytest.mark.skip("Future behavior")
def test_createrepo_writer_rejects_forbidden_structured_chars(tmp_path):
    """Rejects XML-forbidden characters when they cannot be safely stripped."""
    package = _create_unsanitary_package(location_href="packages/\x08legacy-metadata.rpm")

    with cr.RepositoryWriter(str(tmp_path), compression=cr.NO_COMPRESSION) as writer:
        writer.set_num_of_pkgs(1)
        with pytest.raises(cr.CreaterepoCError, match="Forbidden control chars"):
            writer.add_pkg(package.to_createrepo_c())
