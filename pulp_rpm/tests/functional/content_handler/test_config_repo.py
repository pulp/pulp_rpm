import pytest
import requests


@pytest.fixture
def setup_empty_distribution(
    rpm_repository_factory, rpm_publication_factory, rpm_distribution_factory
):
    repo = rpm_repository_factory()
    publication = rpm_publication_factory(repository=repo.pulp_href)
    distribution = rpm_distribution_factory(
        publication=publication.pulp_href, generate_repo_config=True
    )

    return repo, publication, distribution


@pytest.mark.parallel
def test_config_repo_in_listing_unsigned(setup_empty_distribution):
    """Whether the served resources are in the directory listing."""
    _, _, dist = setup_empty_distribution
    content = requests.get(dist.base_url).content

    assert b"config.repo" in content
    assert b"repomd.xml.key" not in content


@pytest.mark.parallel
def test_config_repo_unsigned(setup_empty_distribution):
    """Whether config.repo can be downloaded and has the right content."""
    _, _, dist = setup_empty_distribution
    content = requests.get(f"{dist.base_url}config.repo").content

    assert bytes(f"[{dist.name}]\n", "utf-8") in content
    assert bytes(f"baseurl={dist.base_url}\n", "utf-8") in content
    assert bytes("gpgcheck=0\n", "utf-8") in content
    assert bytes("repo_gpgcheck=0", "utf-8") in content


@pytest.mark.parallel
def test_config_repo_auto_distribute(
    setup_empty_distribution, rpm_publication_api, rpm_distribution_api, monitor_task
):
    """Whether config.repo is properly served using auto-distribute."""
    repo, pub, dist = setup_empty_distribution

    body = {"repository": repo.pulp_href, "publication": None}
    monitor_task(rpm_distribution_api.partial_update(dist.pulp_href, body).task)
    # Check that distribution is now using repository to auto-distribute
    dist = rpm_distribution_api.read(dist.pulp_href)
    assert repo.pulp_href == dist.repository
    assert dist.publication is None
    content = requests.get(f"{dist.base_url}config.repo").content

    assert bytes(f"[{dist.name}]\n", "utf-8") in content
    assert bytes(f"baseurl={dist.base_url}\n", "utf-8") in content
    assert bytes("gpgcheck=0\n", "utf-8") in content
    assert bytes("repo_gpgcheck=0", "utf-8") in content

    # Delete publication and check that 404 is now returned
    rpm_publication_api.delete(pub.pulp_href)
    assert requests.get(f"{dist.base_url}config.repo").status_code == 404
