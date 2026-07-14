"""Tests for repository-level package conflict resolution."""

import enum
import random

import pytest

from pulpcore.client.pulp_rpm import Copy

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


class AddMethod(enum.Enum):
    COPY_API = "copy_api"
    MODIFY_API = "modify_api"


@pytest.fixture(params=[AddMethod.COPY_API, AddMethod.MODIFY_API])
def parametrized_copy_content(
    request, rpm_copy_api, rpm_repository_api, rpm_package_api, monitor_task
):
    """Return a callable that adds all packages from src into dest."""

    def _via_copy(src, dest):
        data = Copy(
            config=[
                {
                    "source_repo_version": src.latest_version_href,
                    "dest_repo": dest.pulp_href,
                }
            ],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

    def _via_modify(src, dest):
        content_hrefs = [
            p.pulp_href
            for p in rpm_package_api.list(repository_version=src.latest_version_href).results
        ]
        response = rpm_repository_api.modify(dest.pulp_href, {"add_content_units": content_hrefs})
        monitor_task(response.task)

    if request.param == AddMethod.COPY_API:
        return _via_copy
    return _via_modify


class TestNvraConflict:
    """Test that NVRA+LOC conflicts are resolved by keeping the highest epoch."""

    @pytest.mark.parallel
    @pytest.mark.parametrize("low_first", [True, False], ids=["low-then-high", "high-then-low"])
    def test_upload_keeps_highest_epoch(
        self,
        tmp_path,
        rpm_repository_factory,
        rpm_repository_api,
        rpm_package_api,
        package_listing: PackageListFetcher,
        monitor_task,
        low_first,
    ):
        """Uploading two RPMs with same NVRA but different epochs keeps the highest."""
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)
        ordered = [low_epoch, high_epoch] if low_first else [high_epoch, low_epoch]

        repo = rpm_repository_factory()
        for pkg in ordered:
            rpm_path = tmp_path / f"epoch-{pkg.nevra.epoch}.rpm"
            build_rpm(pkg.nevra, rpm_path, file_contents=pkg.content)
            monitor_task(rpm_package_api.create(file=str(rpm_path), repository=repo.pulp_href).task)
        repo = rpm_repository_api.read(repo.pulp_href)

        packages = package_listing.from_pulp_repoversion(repo.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 2

    @pytest.mark.parallel
    @pytest.mark.parametrize("low_first", [True, False], ids=["low-then-high", "high-then-low"])
    def test_sync_keeps_highest_epoch(
        self,
        repository_builder: RepositoryBuilder,
        package_listing: PackageListFetcher,
        init_and_sync,
        low_first,
    ):
        """Highest epoch wins regardless of metadata ordering."""
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)
        ordered = [low_epoch, high_epoch] if low_first else [high_epoch, low_epoch]
        remote_repo = repository_builder.build(packages=ordered)

        repository, _ = init_and_sync(url=remote_repo.url, policy="immediate")

        packages = package_listing.from_pulp_repoversion(repository.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 2

    @pytest.mark.parallel
    @pytest.mark.parametrize("low_first", [True, False], ids=["low-then-high", "high-then-low"])
    def test_publish_keeps_highest_epoch(
        self,
        repository_builder: RepositoryBuilder,
        package_listing: PackageListFetcher,
        init_and_sync,
        rpm_publication_factory,
        rpm_distribution_factory,
        low_first,
    ):
        """Published metadata should contain only the highest-epoch package."""
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)
        ordered = [low_epoch, high_epoch] if low_first else [high_epoch, low_epoch]
        remote_repo = repository_builder.build(packages=ordered)

        repository, _ = init_and_sync(url=remote_repo.url, policy="immediate")
        publication = rpm_publication_factory(repository=repository.pulp_href)
        distribution = rpm_distribution_factory(publication=publication.pulp_href)

        metadata_packages = package_listing.from_repository_metadata(url=distribution.base_url)
        assert len(metadata_packages) == 1
        assert metadata_packages[0].nevra.epoch == 2

    @pytest.mark.parallel
    @pytest.mark.parametrize(
        "first_epoch, second_epoch",
        [(0, 2), (2, 0)],
        ids=["low-then-high", "high-then-low"],
    )
    def test_resync_keeps_highest_epoch(
        self,
        repository_builder: RepositoryBuilder,
        package_listing: PackageListFetcher,
        init_and_sync,
        first_epoch,
        second_epoch,
    ):
        """After two syncs with different epochs, the highest epoch is always kept."""
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)
        by_epoch = {0: low_epoch, 2: high_epoch}

        repo_first = repository_builder.build(packages=[by_epoch[first_epoch]])
        repository, _ = init_and_sync(url=repo_first.url, policy="immediate")
        packages = package_listing.from_pulp_repoversion(repository.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == first_epoch

        repo_second = repository_builder.build(packages=[by_epoch[second_epoch]])
        repository, _ = init_and_sync(
            repository=repository, url=repo_second.url, policy="immediate"
        )
        packages = package_listing.from_pulp_repoversion(repository.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 2

    @pytest.mark.parallel
    def test_copy_and_modify_keeps_highest_epoch(
        self,
        repository_builder: RepositoryBuilder,
        package_listing: PackageListFetcher,
        init_and_sync,
        rpm_repository_api,
        parametrized_copy_content,
    ):
        """Adding a lower-epoch package via copy or modify must keep the higher epoch."""
        # NOTE: I'm actually not sure this is what we want... Maybe for "manual" operations
        # like this we want to keep the newer wins strategy?
        low_epoch, high_epoch = make_same_nvra_diff_epoch(epoch_a=0, epoch_b=2)

        repo_high = repository_builder.build(packages=[high_epoch])
        dest, _ = init_and_sync(url=repo_high.url, policy="immediate")

        repo_low = repository_builder.build(packages=[low_epoch])
        src, _ = init_and_sync(url=repo_low.url, policy="immediate")

        # parametrized fixture that calls the copy and the modify api
        parametrized_copy_content(src, dest)

        dest = rpm_repository_api.read(dest.pulp_href)
        packages = package_listing.from_pulp_repoversion(dest.latest_version_href)
        assert len(packages) == 1
        assert packages[0].nevra.epoch == 2
