# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import pytest


from pulpcore.client.pulp_rpm import (
    RpmRepositorySyncURL,
)


@pytest.fixture
def setup_autopublish(rpm_repository_factory, rpm_rpmremote_factory, rpm_distribution_factory):
    """Create remote, repo, publish settings, and distribution."""
    remote = rpm_rpmremote_factory()
    repo = rpm_repository_factory(autopublish=True, checksum_type="sha512")
    distribution = rpm_distribution_factory(repository=repo.pulp_href)

    return repo, remote, distribution


@pytest.mark.parallel
def test_01_sync(setup_autopublish, rpm_repository_api, rpm_publication_api, monitor_task):
    """Assert that syncing the repository triggers auto-publish and auto-distribution."""
    repo, remote, distribution = setup_autopublish
    assert rpm_publication_api.list(repository=repo.pulp_href).count == 0
    assert distribution.publication is None

    # Sync the repository.
    repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    # Check that all the appropriate resources were created
    assert len(task.created_resources) > 1
    publications = rpm_publication_api.list(repository=repo.pulp_href)
    assert publications.count == 1

    # Check that the publish settings were used
    publication = publications.results[0]
    assert publication.checksum_type == "sha512"

    # Sync the repository again. Since there should be no new repository version, there
    # should be no new publications or distributions either.
    sync_response = rpm_repository_api.sync(repo.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert len(task.created_resources) == 0
    assert rpm_publication_api.list(repository=repo.pulp_href).count == 1


@pytest.mark.parallel
def test_02_modify(
    setup_autopublish, rpm_repository_api, rpm_package_api, rpm_publication_api, monitor_task
):
    """Assert that modifying the repository triggers auto-publish and auto-distribution."""
    repo, remote, distribution = setup_autopublish
    assert rpm_publication_api.list(repository=repo.pulp_href).count == 0
    assert distribution.publication is None

    # Modify the repository by adding a content unit
    content = rpm_package_api.list().results[0].pulp_href

    modify_response = rpm_repository_api.modify(repo.pulp_href, {"add_content_units": [content]})
    task = monitor_task(modify_response.task)

    # Check that all the appropriate resources were created
    assert len(task.created_resources) > 1
    publications = rpm_publication_api.list(repository=repo.pulp_href)
    assert publications.count == 1

    # Check that the publish settings were used
    publication = publications.results[0]
    assert publication.checksum_type == "sha512"
