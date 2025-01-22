"""Verify whether package manager, yum/dnf, can consume content from Pulp."""

import subprocess
import itertools

import pytest
import requests

from pulp_rpm.tests.functional.constants import (
    # REPO_WITH_XML_BASE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
)

dnf_installed = subprocess.run(("which", "dnf")).returncode == 0


@pytest.fixture
def dnf_config_add_repo(distribution_base_url):
    added_repos = []

    def _add_repo(distribution, has_signing_service=False):
        subprocess.run(("sudo", "dnf", "config-manager", "--add-repo", distribution.base_url))
        repo_id = "*{}_".format(distribution.base_path)
        args = ["sudo", "dnf", "config-manager", "--save", f"--setopt={repo_id}.gpgcheck=0"]
        if has_signing_service:
            public_key_url = (
                f"{distribution_base_url(distribution.base_url)}repodata/repomd.xml.key"
            )
            args.extend(
                (
                    f"--setopt={repo_id}.repo_gpgcheck=1",
                    f"--setopt={repo_id}.gpgkey={public_key_url}",
                )
            )

        subprocess.run(args + [repo_id])
        added_repos.append(repo_id)

    yield _add_repo
    for repo_id in added_repos:
        subprocess.run(("sudo", "dnf", "config-manager", "--disable", repo_id))


@pytest.fixture
def dnf_install_rpm():
    installed_rpms = []

    def _install(rpm_name):
        result = subprocess.run(("sudo", "dnf", "-y", "install", rpm_name))
        installed_rpms.append(rpm_name)
        return result

    yield _install
    for rpm_name in installed_rpms:
        subprocess.run(("sudo", "dnf", "-y", "remove", rpm_name))


@pytest.fixture
def create_distribution(
    rpm_metadata_signing_service,
    rpm_repository_factory,
    init_and_sync,
    rpm_publication_factory,
    rpm_distribution_factory,
):
    def _create_distribution(
        repo_config=None,
        has_signing_service=False,
        generate_repo_config=False,
        repo_body=None,
        url=RPM_UNSIGNED_FIXTURE_URL,
        policy="on_demand",
        sync_policy="additive",
    ):
        repo_body = repo_body or {}
        if has_signing_service:
            repo_body["metadata_signing_service"] = rpm_metadata_signing_service.pulp_href
        repo = rpm_repository_factory(**repo_body)
        repo, _ = init_and_sync(repository=repo, url=url, policy=policy, sync_policy=sync_policy)

        pub_body = {"repository": repo.pulp_href}
        if repo_config is not None:
            pub_body["repo_config"] = repo_config
        publication = rpm_publication_factory(**pub_body)

        return rpm_distribution_factory(
            publication=publication.pulp_href, generate_repo_config=generate_repo_config
        )

    return _create_distribution


@pytest.mark.skip("TODO: Figure out why sudo suddenly requires a passwd")
@pytest.mark.skipif(not dnf_installed, reason="dnf must be installed")
@pytest.mark.parametrize(
    "policy,sync_policy,url",
    [
        ("on_demand", "mirror_complete", RPM_UNSIGNED_FIXTURE_URL),
        ("streamed", "mirror_complete", RPM_UNSIGNED_FIXTURE_URL),
        ("immediate", "mirror_complete", RPM_UNSIGNED_FIXTURE_URL),
        ("on_demand", "mirror_content_only", RPM_UNSIGNED_FIXTURE_URL),
        ("streamed", "mirror_content_only", RPM_UNSIGNED_FIXTURE_URL),
        ("immediate", "mirror_content_only", RPM_UNSIGNED_FIXTURE_URL),
        ("on_demand", "additive", RPM_UNSIGNED_FIXTURE_URL),
        ("streamed", "additive", RPM_UNSIGNED_FIXTURE_URL),
        ("immediate", "additive", RPM_UNSIGNED_FIXTURE_URL),
        # Skipping until we find an XML base repo we can sync from
        # ("immediate", "mirror_content_only", REPO_WITH_XML_BASE_URL),
    ],
)
def test_package_manager_consume(
    policy,
    sync_policy,
    url,
    dnf_config_add_repo,
    dnf_install_rpm,
    create_distribution,
    pulpcore_bindings,
    delete_orphans_pre,
):
    """Verify whether package manager can consume content from Pulp."""
    before_sync_artifact_count = pulpcore_bindings.ArtifactsApi.list().count

    autopublish = sync_policy != "mirror_complete"
    distribution = create_distribution(
        repo_body={"autopublish": autopublish},
        url=url,
        policy=policy,
        sync_policy=sync_policy,
    )

    before_consumption_artifact_count = pulpcore_bindings.ArtifactsApi.list().count
    # sync=mirror_complete creates new Artifacts for the metadata even w/ on_demand & streamed
    # sync!=mirror_complete sets autopublish=True so new Artifacts will also be created
    assert before_consumption_artifact_count > before_sync_artifact_count

    dnf_config_add_repo(distribution)

    rpm_name = "walrus"
    result = dnf_install_rpm(rpm_name)
    assert result.returncode == 0
    rpm = (
        subprocess.run(("rpm", "-q", rpm_name), capture_output=True)
        .stdout.decode("utf-8")
        .strip()
        .split("-")
    )
    assert rpm_name == rpm[0]

    after_consumption_artifact_count = pulpcore_bindings.ArtifactsApi.list().count
    if policy == "immediate" or policy == "streamed":
        assert before_consumption_artifact_count == after_consumption_artifact_count
    elif policy == "on_demand":
        assert after_consumption_artifact_count > before_consumption_artifact_count


@pytest.mark.skip("TODO: Figure out why sudo suddenly requires a passwd")
@pytest.mark.parallel
def test_publish_signed_repo_metadata(
    rpm_metadata_signing_service, create_distribution, dnf_config_add_repo, dnf_install_rpm
):
    """Test if a package manager is able to install packages from a signed repository."""
    if rpm_metadata_signing_service is None:
        pytest.skip("Need a signing service for this test")

    distribution = create_distribution(repo_config={}, has_signing_service=True)
    dnf_config_add_repo(distribution, has_signing_service=True)

    rpm_name = "walrus"
    result = dnf_install_rpm(rpm_name)
    assert result.returncode == 0
    rpm = (
        subprocess.run(("rpm", "-q", rpm_name), capture_output=True)
        .stdout.decode("utf-8")
        .strip()
        .split("-")
    )
    assert rpm_name == rpm[0]


# Test all possible combinations of options made to a publication.
test_options = {
    "repo_config": [{}, {"assumeyes": True, "gpgcheck": 1}],
    "has_signing_service": [True, False],
    "generate_repo_config": [True, False],
}
func_params = itertools.product(*test_options.values())


@pytest.mark.parallel
@pytest.mark.parametrize("repo_config,has_signing_service,generate_repo_config", func_params)
def test_config_dot_repo(
    distribution_base_url,
    repo_config,
    has_signing_service,
    generate_repo_config,
    rpm_metadata_signing_service,
    create_distribution,
):
    """Test if the generated config.repo has the right content."""
    if has_signing_service and rpm_metadata_signing_service is None:
        pytest.skip("Need a signing service for this test")
    if not generate_repo_config:
        pytest.skip("Generation of config.repo file was disabled")

    distribution = create_distribution(
        repo_config=repo_config,
        has_signing_service=has_signing_service,
        generate_repo_config=generate_repo_config,
    )
    content = requests.get(f"{distribution_base_url(distribution.base_url)}config.repo").text
    assert f"[{distribution.name}]\n" in content
    assert f"baseurl={distribution_base_url(distribution.base_url)}\n" in content
    assert "gpgcheck=0\n" in content
    assert "repo_gpgcheck=0\n" in content

    if has_signing_service:
        assert (
            f"gpgkey={distribution_base_url(distribution.base_url)}repodata/repomd.xml.key"
            in content
        )

    if repo_config:
        assert "assumeyes=True\n" in content
        assert "gpgcheck=1\n" in content


@pytest.mark.parallel
def test_repomd_headers(create_distribution, distribution_base_url):
    """Test if repomd.xml is returned with Cache-control: no-cache header."""
    distribution = create_distribution(
        repo_config={}, has_signing_service=True, generate_repo_config=True
    )
    resp = requests.get(f"{distribution_base_url(distribution.base_url)}/repodata/repomd.xml")
    assert resp.headers.get("Cache-control", "") == "no-cache"

    resp = requests.get(f"{distribution_base_url(distribution.base_url)}/config.repo")
    assert not resp.headers.get("Cache-control", "") == "no-cache"

    resp = requests.get(f"{distribution_base_url(distribution.base_url)}/repodata/repomd.xml.key")
    assert resp.headers.get("Cache-control", "") == "no-cache"
