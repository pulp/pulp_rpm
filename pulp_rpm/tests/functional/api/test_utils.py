"""Tests for test utility classes (RepositoryBuilder, PackageListFetcher, etc.)."""

from pulp_rpm.tests.functional.utils import (
    MetaPackage,
    PackageListFetcher,
    RepositoryBuilder,
    normalized_location,
)


def test_repository_builder(
    repository_builder: RepositoryBuilder, package_listing: PackageListFetcher
):
    """RepositoryBuilder produces a valid local repo that PackageListFetcher can parse."""
    pkg = MetaPackage(
        nevra=MetaPackage.generate_nevra(1),
        digest=MetaPackage.generate_digest(1),
        time_build=1,
        location="pkg1-1.0-1.noarch.rpm",
    )
    remote_repo = repository_builder.build(packages=[pkg])
    entries = package_listing.from_repository_metadata(url=remote_repo.url).filter(
        name=pkg.nevra.name
    )
    assert len(entries) == 1
    assert entries[0].digest == pkg.digest


def test_repository_builder_multiple_packages(
    repository_builder: RepositoryBuilder, package_listing: PackageListFetcher
):
    """All packages added to RepositoryBuilder are discoverable in the resulting repo."""
    pkgs = [
        MetaPackage(
            nevra=MetaPackage.generate_nevra(i),
            digest=MetaPackage.generate_digest(i),
            time_build=i,
            location=f"pkg{i}-{i}.0-{i}.noarch.rpm",
        )
        for i in range(1, 4)
    ]
    remote_repo = repository_builder.build(packages=pkgs)
    all_entries = package_listing.from_repository_metadata(url=remote_repo.url)
    found_digests = {e.digest for e in all_entries}
    assert {p.digest for p in pkgs} == found_digests


def test_package_list_filter_is_exclusive(
    repository_builder: RepositoryBuilder, package_listing: PackageListFetcher
):
    """PackageList.filter returns only packages with the requested name."""
    pkg_a = MetaPackage(
        nevra=MetaPackage.generate_nevra(1),
        digest=MetaPackage.generate_digest(1),
        time_build=1,
        location="a-1.0-1.noarch.rpm",
    )
    pkg_b = MetaPackage(
        nevra=MetaPackage.generate_nevra(2),
        digest=MetaPackage.generate_digest(2),
        time_build=2,
        location="b-2.0-2.noarch.rpm",
    )
    remote_repo = repository_builder.build(packages=[pkg_a, pkg_b])
    entries = package_listing.from_repository_metadata(url=remote_repo.url)

    assert len(entries.filter(name=pkg_a.nevra.name)) == 1
    assert len(entries.filter(name="nonexistent")) == 0


def test_normalized_location():
    """normalized_location produces the canonical Packages/<initial>/<nvra>.rpm path."""
    pkg = MetaPackage(
        nevra=MetaPackage.generate_nevra(1),
        digest=MetaPackage.generate_digest(1),
        time_build=1,
        location="original-location.rpm",
    )
    nvra = pkg.nevra.to_nvra()

    with_prefix = normalized_location(pkg, prefix=True)
    assert with_prefix.location == f"Packages/{pkg.nevra.name[0]}/{nvra}.rpm"

    without_prefix = normalized_location(pkg, prefix=False)
    assert without_prefix.location == f"{nvra}.rpm"
