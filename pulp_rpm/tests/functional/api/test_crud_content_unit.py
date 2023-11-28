"""Tests that perform actions over content unit."""
from urllib.parse import urljoin

import pytest
import requests

from pulp_rpm.tests.functional.utils import gen_rpm_content_attrs
from pulp_rpm.tests.functional.constants import (
    RPM_KICKSTART_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_REPO_METADATA_FIXTURE_URL,
    RPM_PACKAGE_FILENAME,
    RPM_PACKAGE_FILENAME2,
)


def test_crud_content_unit(
    delete_orphans_pre,
    signed_artifact,
    gen_object_with_cleanup,
    rpm_package_api,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_repository_version_api,
    monitor_task,
):
    """Test creating, reading, updating, and deleting a content unit of package type."""
    # Create content unit
    content_unit_original = {}

    attrs = gen_rpm_content_attrs(signed_artifact, RPM_PACKAGE_FILENAME)
    response = rpm_package_api.create(**attrs)
    content_unit = rpm_package_api.read(monitor_task(response.task).created_resources[0])
    # rpm package doesn't keep relative_path but the location href
    del attrs["relative_path"]

    content_unit_original.update(content_unit.to_dict())
    for key, val in attrs.items():
        assert content_unit_original[key] == val

    # Read a content unit by its href
    content_unit = rpm_package_api.read(content_unit_original["pulp_href"]).to_dict()
    for key, val in content_unit_original.items():
        assert content_unit[key] == val

    # Read a content unit by its pkg_id
    page = rpm_package_api.list(pkg_id=content_unit_original["pkg_id"])
    assert len(page.results) == 1
    for key, val in content_unit_original.items():
        assert page.results[0].to_dict()[key] == val

    # Attempt to update a content unit using HTTP PATCH
    attrs = gen_rpm_content_attrs(signed_artifact, RPM_PACKAGE_FILENAME2)
    with pytest.raises(AttributeError) as exc:
        rpm_package_api.partial_update(content_unit_original["pulp_href"], attrs)
    msg = "object has no attribute 'partial_update'"
    assert msg in str(exc)

    # Attempt to update a content unit using HTTP PUT
    attrs = gen_rpm_content_attrs(signed_artifact, RPM_PACKAGE_FILENAME2)
    with pytest.raises(AttributeError) as exc:
        rpm_package_api.update(content_unit_original["pulp_href"], attrs)
    msg = "object has no attribute 'update'"
    assert msg in str(exc)

    # Attempt to delete a content unit using HTTP DELETE
    with pytest.raises(AttributeError) as exc:
        rpm_package_api.delete(content_unit_original["pulp_href"])
    msg = "object has no attribute 'delete'"
    assert msg in str(exc)

    # Attempt to create duplicate package without specifying a repository
    attrs = gen_rpm_content_attrs(signed_artifact, RPM_PACKAGE_FILENAME)
    response = rpm_package_api.create(**attrs)
    duplicate = rpm_package_api.read(monitor_task(response.task).created_resources[0])
    assert duplicate.pulp_href == content_unit_original["pulp_href"]

    # Attempt to create duplicate package while specifying a repository
    repo = rpm_repository_factory()
    attrs = gen_rpm_content_attrs(signed_artifact, RPM_PACKAGE_FILENAME)
    attrs["repository"] = repo.pulp_href
    response = rpm_package_api.create(**attrs)
    monitored_response = monitor_task(response.task)

    duplicate = rpm_package_api.read(monitored_response.created_resources[1])
    assert duplicate.pulp_href == content_unit_original["pulp_href"]

    repo = rpm_repository_api.read(repo.pulp_href)
    assert repo.latest_version_href.endswith("/versions/1/")

    version = rpm_repository_version_api.read(repo.latest_version_href)
    assert version.content_summary.present["rpm.package"]["count"] == 1
    assert version.content_summary.added["rpm.package"]["count"] == 1


@pytest.mark.parallel
@pytest.mark.parametrize(
    "url",
    [RPM_MODULAR_FIXTURE_URL, RPM_KICKSTART_FIXTURE_URL, RPM_REPO_METADATA_FIXTURE_URL],
    ids=["MODULAR_FIXTURE_URL", "KICKSTART_FIXTURE_URL", "REPO_METADATA_FIXTURE_URL"],
)
def test_remove_content_unit(url, init_and_sync, rpm_repository_version_api, bindings_cfg):
    """
    Sync a repository and test that content of any type cannot be removed directly.

    - advisory
    - distribution_tree
    - modulemd
    - modulemd_defaults
    - package
    - packagecategory
    - packageenvironment
    - packagegroup
    - packagelangpacks
    - repo metadata
    """
    repo, _ = init_and_sync(url=url, policy="on_demand")

    # Test remove content by types contained in repository.
    version = rpm_repository_version_api.read(repo.latest_version_href)

    # iterate over content filtered by repository versions
    for content_units in version.content_summary.added.values():
        auth = (bindings_cfg.username, bindings_cfg.password)
        url = urljoin(bindings_cfg.host, content_units["href"])
        response = requests.get(url, auth=auth).json()

        # iterate over particular content units and issue delete requests
        for content_unit in response["results"]:
            url = urljoin(bindings_cfg.host, content_unit["pulp_href"])
            resp = requests.delete(url, auth=auth)

            # check that '405' (method not allowed) is returned
            assert resp.status_code == 405
