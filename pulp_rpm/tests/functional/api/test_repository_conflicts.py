"""Tests for repository-level package conflict resolution."""

import random

import pytest

from pulp_rpm.tests.functional.utils import (
    MetaPackage,
    Nevra,
    PackageListFetcher,
    RepositoryBuilder,
    build_rpm,
)


def make_same_nvra_diff_epoch(epoch_a, epoch_b, build_time_a=1, build_time_b=1):
    """Create two MetaPackages sharing the same NVRA but with different epochs."""
    n = random.randint(1000, 999_999)
    base = MetaPackage.generate_nevra(n)
    nvra = base.to_nvra()
    pkg_a = MetaPackage(
        nevra=Nevra(base.name, epoch_a, base.version, base.release, base.arch),
        time_build=build_time_a,
        location=f"{nvra}-a.rpm",
        content=f"pkg-{n}-epoch-{epoch_a}".encode(),
    )
    pkg_b = MetaPackage(
        nevra=Nevra(base.name, epoch_b, base.version, base.release, base.arch),
        time_build=build_time_b,
        location=f"{nvra}-b.rpm",
        content=f"pkg-{n}-epoch-{epoch_b}".encode(),
    )
    return pkg_a, pkg_b


class TestNvraConflict:
    """Test that NVRA+LOC conflicts are resolved by keeping the highest epoch.

    This purposely doesn't comprehensivle test all ingestion methods, as all of these goes through
    finalizing a repository version. Instead, we unit test the deduplication logic used in the finalization
    step, where it's easier to be more comprehensive about conflict cases coverage.
    """

    @pytest.mark.parallel
    def test_upload_keeps_highest_epoch(
        self,
        tmp_path,
        rpm_repository_factory,
        rpm_repository_api,
        rpm_package_api,
        package_listing: PackageListFetcher,
        monitor_task,
    ):
        """Uploading two RPMs with same NVRA but different epochs keeps the highest."""
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)

        repo = rpm_repository_factory()
        for pkg in [low_epoch, high_epoch]:
            rpm_path = tmp_path / f"epoch-{pkg.nevra.epoch}.rpm"
            build_rpm(pkg.nevra, rpm_path, file_contents=pkg.content)
            monitor_task(rpm_package_api.create(file=str(rpm_path), repository=repo.pulp_href).task)
        repo = rpm_repository_api.read(repo.pulp_href)

        packages = package_listing.from_pulp_repoversion(repo.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 2

    @pytest.mark.parallel
    def test_resync_keeps_highest_epoch(
        self,
        repository_builder: RepositoryBuilder,
        package_listing: PackageListFetcher,
        init_and_sync,
    ):
        """After two syncs with different epochs, the highest epoch is always kept."""
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)

        repo_first = repository_builder.build(packages=[low_epoch])
        repository, _ = init_and_sync(url=repo_first.url, policy="immediate")
        packages = package_listing.from_pulp_repoversion(repository.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 0

        repo_second = repository_builder.build(packages=[high_epoch])
        repository, _ = init_and_sync(
            repository=repository, url=repo_second.url, policy="immediate"
        )
        packages = package_listing.from_pulp_repoversion(repository.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 2


@pytest.mark.parallel
def test_modify_with_resigned_packages_from_two_repositories(
    repository_builder,
    init_and_sync,
    monitor_task,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_package_api,
):
    """A single modify request can combine two checksums of the same package."""
    nevra = MetaPackage.generate_nevra(random.randint(1000, 999_999))
    location = f"Packages/{nevra.name[0]}/{nevra.to_nvra()}.rpm"
    source_packages = []
    for digest in ("a" * 64, "f" * 64):
        remote_repo = repository_builder.build(
            packages=[MetaPackage(nevra, time_build=1000, location=location, digest=digest)]
        )
        source_repo, _ = init_and_sync(url=remote_repo.url, policy="on_demand")
        package = rpm_package_api.list(repository_version=source_repo.latest_version_href).results[
            0
        ]
        assert package.pkg_id == digest
        source_packages.append(package)

    assert source_packages[0].location_href == source_packages[1].location_href
    destination = rpm_repository_factory()
    response = rpm_repository_api.modify(
        destination.pulp_href,
        {"add_content_units": [package.pulp_href for package in source_packages]},
    )
    monitor_task(response.task)

    destination = rpm_repository_api.read(destination.pulp_href)
    packages = rpm_package_api.list(repository_version=destination.latest_version_href).results
    assert len(packages) == 1
    assert packages[0].pkg_id == "f" * 64
