import os

from xml.etree import ElementTree

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL, RpmRpmPublication, RpmRpmDistribution

from pulp_smash.utils import http_get
from pulp_smash.pulp3.utils import gen_repo, get_content
from pulp_smash.pulp3.bindings import monitor_task

from pulp_rpm.tests.functional.constants import MODULEMD_FIELDS
from pulp_rpm.tests.functional.utils import gen_rpm_remote, read_xml_gz
from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_SUMMARY,
    RPM_MODULAR_FIXTURE_URL,
    RPM_NAMESPACES,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_SIGNED_FIXTURE_URL,
)


def test_is_modular_flag(
    delete_orphans_pre,
    gen_object_with_cleanup,
    rpm_package_api,
    rpm_repository_api,
    rpm_rpmremote_api,
):
    """
    Test package is marked as modular when synced from modular repository.
    """

    remote_data = gen_rpm_remote(RPM_SIGNED_FIXTURE_URL)
    remote = gen_object_with_cleanup(rpm_rpmremote_api, remote_data)
    repo_data = gen_repo(remote=remote.pulp_href)
    repo = gen_object_with_cleanup(rpm_repository_api, repo_data)
    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, sync_url)
    monitor_task(sync_response.task)

    # assert no package is marked modular
    assert rpm_package_api.list().count == RPM_FIXTURE_SUMMARY[RPM_PACKAGE_CONTENT_NAME]
    for pkg in get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
        assert pkg["is_modular"] is False

    remote_modular_data = gen_rpm_remote(RPM_MODULAR_FIXTURE_URL)
    remote_modular = gen_object_with_cleanup(rpm_rpmremote_api, remote_modular_data)
    repo_modular_data = gen_repo(remote=remote_modular.pulp_href)
    repo_modular = gen_object_with_cleanup(rpm_repository_api, repo_modular_data)
    sync_url = RpmRepositorySyncURL(remote=remote_modular.pulp_href)
    sync_response = rpm_repository_api.sync(repo_modular.pulp_href, sync_url)
    monitor_task(sync_response.task)

    # assert all package from modular repo is marked as modular
    for pkg in get_content(repo_modular.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
        assert pkg["is_modular"] is True


def test_modulemd_fields_exposed(
    delete_orphans_pre,
    gen_object_with_cleanup,
    rpm_modulemd_api,
    rpm_package_api,
    rpm_repository_api,
    rpm_rpmremote_api,
):
    """Test if profile and description info is exposed."""
    remote_data = gen_rpm_remote(RPM_MODULAR_FIXTURE_URL)
    remote = gen_object_with_cleanup(rpm_rpmremote_api, remote_data)
    repo_data = gen_repo(remote=remote.pulp_href)
    repo = gen_object_with_cleanup(rpm_repository_api, repo_data)
    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, sync_url)
    monitor_task(sync_response.task)
    modulemd_href = [md.pulp_href for md in rpm_modulemd_api.list().results if md.name == "dwm"][0]
    modulemd = rpm_modulemd_api.read(modulemd_href)
    # Check if all fields are exposed
    assert sorted(list(modulemd.to_dict().keys())) == MODULEMD_FIELDS


def test_modular_yaml(
    delete_orphans_pre,
    gen_object_with_cleanup,
    rpm_repository_api,
    rpm_rpmremote_api,
    rpm_publication_api,
    rpm_distribution_api,
):
    """Test that modules.yaml is generated correctly."""

    def _get_modules_yaml_path(repomd_url):
        """Helper function to get url of modules.yaml from repository."""
        repomd_file_url = os.path.join(repomd_url, "repodata/repomd.xml")
        xml = http_get(repomd_file_url).decode()
        tree = ElementTree.fromstring(xml)
        xpath = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
        data_elems = [elem for elem in tree.findall(xpath) if elem.get("type") == "modules"]
        xpath = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
        location_href = data_elems[0].find(xpath).get("href")

        return location_href

    def _compare_modules(original_modules_url, pulp_generated_modules_url):
        """Compare..."""
        original_xml_content = http_get(original_modules_url)
        original_xml = read_xml_gz(original_xml_content).decode()

        original_list = sorted(original_xml.split("---")[1:])

        pulp_xml = http_get(pulp_generated_modules_url).decode()
        pulp_list = sorted(pulp_xml.split("---")[1:])

        assert len(pulp_list) == len(original_list)
        assert pulp_list == original_list

    dist_name = "modular-test-distribution"
    remote_data = gen_rpm_remote(RPM_MODULAR_FIXTURE_URL)
    remote = gen_object_with_cleanup(rpm_rpmremote_api, remote_data)

    repo_data = gen_repo(remote=remote.pulp_href)
    repo = gen_object_with_cleanup(rpm_repository_api, repo_data)

    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, sync_url)
    monitor_task(sync_response.task)

    repo = rpm_repository_api.read(repo.pulp_href)
    publish_data = RpmRpmPublication(repository=repo.pulp_href)
    publish_response = rpm_publication_api.create(publish_data)
    created_resources = monitor_task(publish_response.task).created_resources
    publication = rpm_publication_api.read(created_resources[0])

    dist_data = RpmRpmDistribution(
        name=dist_name, publication=publication.pulp_href, base_path=dist_name
    )
    res = rpm_distribution_api.create(dist_data)
    distribution = rpm_distribution_api.read(monitor_task(res.task).created_resources[0])

    pulp_modules_yaml_url = os.path.join(
        distribution.base_url, _get_modules_yaml_path(distribution.base_url)
    )
    original_modules_yaml_url = os.path.join(remote.url, _get_modules_yaml_path(remote.url))

    _compare_modules(original_modules_yaml_url, pulp_modules_yaml_url)

    # cleanup
    rpm_distribution_api.delete(distribution.pulp_href)
    rpm_publication_api.delete(publication.pulp_href)
