"""Parity tests for conversion of RPM metadata parsed by supported libraries."""

import createrepo_c as cr
from rpm_rs import DependencyFlags, FileOptions, PackageBuilder

from pulp_rpm.app.models import Package
from pulp_rpm.app.shared_utils import read_package_from_file


def _write_rpm(tmp_path, name, builder):
    """Build *builder* and return the path to its RPM file."""
    path = tmp_path / f"{name}.rpm"
    path.write_bytes(builder.build().to_bytes())
    return path


def _assert_conversion_parity(
    path, *, changelog_limit=None, tuple_cache=None, string_cache=None, signing_keys=None
):
    """Assert that both parsers produce identical Package initialization data."""
    createrepo_kwargs = {"changelog_limit": changelog_limit} if changelog_limit is not None else {}
    createrepo_package = cr.package_from_rpm(str(path), **createrepo_kwargs)
    rpmrepo_package = read_package_from_file(path)
    # An RPM does not contain its repository location. rpmrepo_metadata defaults it to the
    # file name, while Pulp's createrepo_c callers set it from their source context.
    createrepo_package.location_href = rpmrepo_package.location_href

    createrepo_dict = Package.createrepo_to_dict(
        createrepo_package,
        tuple_cache=tuple_cache,
        string_cache=string_cache,
        signing_keys=signing_keys,
    )
    rpmrepo_dict = Package.rpmrepo_to_dict(
        rpmrepo_package,
        tuple_cache=tuple_cache,
        string_cache=string_cache,
        signing_keys=signing_keys,
    )
    assert createrepo_dict == rpmrepo_dict
    return createrepo_dict, rpmrepo_dict


def test_package_conversion_matches_for_minimal_rpm(tmp_path):
    """Matches complete conversion output for an RPM with only required metadata."""
    path = _write_rpm(
        tmp_path,
        "minimal-1.0-1.noarch",
        PackageBuilder("minimal", "1.0", "MIT", "noarch"),
    )

    createrepo_dict, rpmrepo_dict = _assert_conversion_parity(path)

    # rpmrepo_metadata represents epoch as an integer and missing scalar tags as empty strings;
    # createrepo_c uses a string epoch and None. Pulp's initialization data has one canonical form.
    assert createrepo_dict is not rpmrepo_dict
    assert rpmrepo_dict["epoch"] == "0"
    assert rpmrepo_dict["summary"] == ""
    assert rpmrepo_dict["description"] == ""
    assert rpmrepo_dict["url"] == ""
    assert rpmrepo_dict["rpm_buildhost"] == ""
    assert rpmrepo_dict["rpm_packager"] == ""
    assert rpmrepo_dict["rpm_vendor"] == ""


def test_package_conversion_matches_for_rich_rpm(tmp_path):
    """Matches complete output for metadata, all dependency types, files, and changelogs."""
    builder = PackageBuilder("rich", "2.3.4", "MPL-2.0", "x86_64")
    builder.release("5.el10")
    builder.epoch(2)
    builder.description("A complete conversion-parity fixture.")
    builder.url("https://example.invalid/rich")
    builder.vendor("Parity Vendor")
    builder.packager("Parity Packager <packager@example.invalid>")
    builder.group("Development/Tools")
    builder.build_host("builder.example.invalid")

    builder.provides("rich-capability", "2.3.4-5.el10", DependencyFlags.EQUAL)
    builder.requires("runtime", "1.0", DependencyFlags.GREATER | DependencyFlags.EQUAL)
    builder.requires("pre-runtime", "2", DependencyFlags.PREREQ | DependencyFlags.EQUAL)
    builder.conflicts("old-rich", "2.0", DependencyFlags.LESS)
    builder.obsoletes("obsolete-rich", "1.0", DependencyFlags.LESS | DependencyFlags.EQUAL)
    builder.recommends("recommended-rich", "3", DependencyFlags.EQUAL)
    builder.suggests("suggested-rich")
    builder.enhances("enhanced-rich", "1", DependencyFlags.GREATER)
    builder.supplements("supplemented-rich", "4", DependencyFlags.EQUAL)

    builder.add_changelog_entry("Older Author", "Older change", 1_600_000_000)
    builder.add_changelog_entry("Newer Author", "Newer change", 1_700_000_000)
    builder.with_file_contents(
        b"#!/bin/sh\necho rich\n",
        FileOptions.new("/usr/bin/rich", permissions=0o755),
    )
    builder.with_file_contents(b"setting=true\n", FileOptions.new("/etc/rich.conf", config=True))
    builder.with_dir_entry(FileOptions.dir("/usr/share/rich", permissions=0o755))
    builder.with_symlink(FileOptions.symlink("/usr/bin/rich-link", "/usr/bin/rich"))
    builder.with_ghost(FileOptions.ghost("/var/lib/rich/state", permissions=0o644))
    path = _write_rpm(tmp_path, "rich-2.3.4-5.el10.x86_64", builder)

    _assert_conversion_parity(path)


def test_package_conversion_matches_with_caches_and_signing_keys(tmp_path):
    """Matches output when file-interning caches and signing-key metadata are supplied."""
    builder = PackageBuilder("cached", "1.0", "MIT", "noarch")
    builder.with_file_contents(b"one", FileOptions.new("/usr/lib/cached/one"))
    builder.with_file_contents(b"two", FileOptions.new("/usr/lib/cached/two"))
    path = _write_rpm(tmp_path, "cached-1.0-1.noarch", builder)

    tuple_cache = {}
    string_cache = {}
    signing_keys = ["0123456789ABCDEF", "FEDCBA9876543210"]

    createrepo_dict, rpmrepo_dict = _assert_conversion_parity(
        path,
        tuple_cache=tuple_cache,
        string_cache=string_cache,
        signing_keys=signing_keys,
    )
    assert tuple_cache
    assert string_cache
    assert createrepo_dict["files"][0] is rpmrepo_dict["files"][0]
    assert createrepo_dict["files"][0][1] is rpmrepo_dict["files"][0][1]


def test_package_conversion_keeps_only_configured_recent_changelogs(tmp_path, monkeypatch):
    """Applies Pulp's configured changelog retention identically with either parser."""
    builder = PackageBuilder("changelog-limit", "1.0", "MIT", "noarch")
    builder.add_changelog_entry("Newest", "third", 1_700_000_000)
    builder.add_changelog_entry("Oldest", "first", 1_500_000_000)
    builder.add_changelog_entry("Middle", "second", 1_600_000_000)
    path = _write_rpm(tmp_path, "changelog-limit-1.0-1.noarch", builder)

    monkeypatch.setattr("pulp_rpm.app.models.package.KEEP_CHANGELOG_LIMIT", 2)
    monkeypatch.setattr("pulp_rpm.app.shared_utils.settings.KEEP_CHANGELOG_LIMIT", 2)

    _assert_conversion_parity(path, changelog_limit=2)


def test_package_conversion_matches_for_ghost_directory(tmp_path):
    """Matches createrepo_c's directory classification for a ghost directory."""
    builder = PackageBuilder("ghost-directory", "1.0", "MIT", "noarch")
    builder.with_ghost(FileOptions.ghost_dir("/var/cache/ghost-directory", permissions=0o755))
    path = _write_rpm(tmp_path, "ghost-directory-1.0-1.noarch", builder)

    _assert_conversion_parity(path)
