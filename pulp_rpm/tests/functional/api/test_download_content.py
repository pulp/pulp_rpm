"""Tests that verify download of content served by Pulp."""

import hashlib
import time
from random import choice
from dataclasses import dataclass
from urllib.parse import urljoin

import pytest
import requests
from django.conf import settings

from pulp_rpm.tests.functional.constants import RPM_UNSIGNED_FIXTURE_URL
from pulp_rpm.tests.functional.utils import (
    get_package_repo_path,
)
from pulpcore.client.pulp_rpm import RpmRpmPublication, RpmRpmDistribution


@pytest.mark.parallel
def test_all(
    rpm_unsigned_repo_immediate,
    rpm_package_api,
    rpm_publication_api,
    rpm_distribution_factory,
    download_content_unit,
    gen_object_with_cleanup,
):
    """Verify whether content served by pulp can be downloaded.

    The process of publishing content is more involved in Pulp 3 than it
    was under Pulp 2. Given a repository, the process is as follows:

    1. Create a publication from the repository. (The latest repository
       version is selected if no version is specified.) A publication is a
       repository version plus metadata.
    2. Create a distribution from the publication. The distribution defines
       at which URLs a publication is available, e.g.
       ``http://example.com/content/foo/`` and
       ``http://example.com/content/bar/``.

    Do the following:

    1. Create, populate, publish, and distribute a repository.
    2. Select a random content unit in the distribution. Download that
       content unit from Pulp, and verify that the content unit has the
       same checksum when fetched directly from Pulp-Fixtures.
    """
    # Sync a Repository
    repo = rpm_unsigned_repo_immediate

    # Create a publication.
    publish_data = RpmRpmPublication(repository=repo.pulp_href)
    publication = gen_object_with_cleanup(rpm_publication_api, publish_data)

    # Create a distribution.
    distribution = rpm_distribution_factory(publication=publication.pulp_href)

    # Pick a content unit (of each type), and download it from both Pulp Fixtures…
    packages = rpm_package_api.list(repository_version=repo.latest_version_href)
    package_paths = [p.location_href for p in packages.results]
    unit_path = choice(package_paths)
    fixture_hash = hashlib.sha256(
        requests.get(urljoin(RPM_UNSIGNED_FIXTURE_URL, unit_path)).content
    ).hexdigest()

    # …and Pulp.
    pkg_path = get_package_repo_path(unit_path)
    content = download_content_unit(distribution.base_path, pkg_path)
    pulp_hash = hashlib.sha256(content).hexdigest()

    assert fixture_hash == pulp_hash


@dataclass
class DistributionStabilityContext:
    pub_with_pkg: RpmRpmPublication
    pub_without_pkg: RpmRpmPublication

    def create_distribution(self, publication: RpmRpmPublication) -> RpmRpmDistribution:
        pass

    def update_distribution(self, dist: RpmRpmDistribution, publication: RpmRpmPublication):
        pass

    def get_pkg_url(self, distribution: RpmRpmDistribution) -> str:
        pass

    def clear_dist_cache(self, dist: RpmRpmDistribution) -> None:
        pass


class Clock:
    def __init__(self):
        self._start = None

    def __enter__(self) -> "Clock":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_) -> None:
        pass

    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def wait_until(self, t: float) -> None:
        remaining = t - self.elapsed()
        if remaining > 0:
            time.sleep(remaining)


class TestDistributionStability:
    @pytest.mark.parallel
    def test_distribution_serves_old_content_during_cache_grace_period(
        self,
        ctx: DistributionStabilityContext,
    ):
        assert settings.RPM_PUBLICATION_CACHE_DURATION < 10, "Retention time too long for testing."
        dist = ctx.create_distribution(publication=ctx.pub_with_pkg)
        pkg_url = ctx.get_pkg_url(dist)
        assert requests.get(pkg_url).status_code == 200

        with Clock() as clock:
            ctx.update_distribution(dist, publication=ctx.pub_without_pkg)

            # Old content must be served within the retention period
            assert requests.get(pkg_url).status_code == 200
            assert clock.elapsed() < settings.RPM_PUBLICATION_CACHE_DURATION

            # Old content must be unavailable after the retention period
            clock.wait_until(settings.RPM_PUBLICATION_CACHE_DURATION)
            ctx.clear_dist_cache(dist)  # redis cache will interfere with our assertion
            assert clock.elapsed() > settings.RPM_PUBLICATION_CACHE_DURATION
            response = requests.get(pkg_url)
            assert response.status_code == 404

    @pytest.fixture
    def ctx(
        self,
        init_and_sync,
        distribution_base_url,
        rpm_package_api,
        rpm_publication_factory,
        rpm_distribution_factory,
        rpm_repository_api,
        rpm_distribution_api,
        monitor_task,
    ) -> DistributionStabilityContext:
        """Set up two publications and methods for managing distribution."""
        # Create first publication which contains a given pkg
        repo, _ = init_and_sync()
        pub_with_pkg = rpm_publication_factory(repository=repo.pulp_href)

        packages = rpm_package_api.list(repository_version=repo.latest_version_href)
        pkg = packages.results[0]
        pkg_repo_path = get_package_repo_path(pkg.location_href)

        # Remove package from repository
        monitor_task(
            rpm_repository_api.modify(
                repo.pulp_href, {"remove_content_units": [pkg.pulp_href]}
            ).task
        )

        # Create publication which does not contain the pkg
        pub_without_pkg = rpm_publication_factory(repository=repo.pulp_href)

        class _DistributionStabilityContext(DistributionStabilityContext):
            def create_distribution(self, publication: RpmRpmPublication) -> RpmRpmDistribution:
                return rpm_distribution_factory(publication=publication.pulp_href)

            def update_distribution(
                self, dist: RpmRpmDistribution, publication: RpmRpmPublication
            ) -> None:
                monitor_task(
                    rpm_distribution_api.partial_update(
                        dist.pulp_href, {"publication": publication.pulp_href}
                    ).task
                )

            def get_pkg_url(self, dist: RpmRpmDistribution) -> str:
                return urljoin(distribution_base_url(dist.base_url), pkg_repo_path)

            def clear_dist_cache(self, dist: RpmRpmDistribution) -> None:
                original_base_path = dist.base_path
                tmp_base_path = original_base_path + "-tmp"
                monitor_task(
                    rpm_distribution_api.partial_update(
                        dist.pulp_href, {"base_path": tmp_base_path}
                    ).task
                )
                monitor_task(
                    rpm_distribution_api.partial_update(
                        dist.pulp_href, {"base_path": original_base_path}
                    ).task
                )
                restored = rpm_distribution_api.read(dist.pulp_href)
                assert restored.base_path == original_base_path

        return _DistributionStabilityContext(
            pub_with_pkg=pub_with_pkg,
            pub_without_pkg=pub_without_pkg,
        )
