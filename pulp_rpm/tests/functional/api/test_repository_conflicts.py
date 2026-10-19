"""Tests for repository-level package conflict resolution."""

import random

import pytest

from pulp_rpm.tests.functional.utils import MetaPackage


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
