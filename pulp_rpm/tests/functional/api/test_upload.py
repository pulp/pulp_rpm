"""Tests that perform actions over content unit."""

import os
from tempfile import NamedTemporaryFile

import pytest
import requests

from pulpcore.client.pulpcore.exceptions import BadRequestException
from pulpcore.client.pulp_rpm import ApiException
from pulpcore.tests.functional.utils import PulpTaskError
from pulp_rpm.tests.functional.constants import (
    BIG_COMPS_XML,
    BIG_CATEGORY,
    BIG_GROUPS,
    BIG_ENVIRONMENTS,
    BIG_LANGPACK,
    RPM_PACKAGEENVIRONMENT_CONTENT_NAME,
    RPM_PACKAGECATEGORY_CONTENT_NAME,
    RPM_PACKAGEGROUP_CONTENT_NAME,
    RPM_PACKAGELANGPACKS_CONTENT_NAME,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_PACKAGE_FILENAME,
    RPM_PACKAGE_FILENAME2,
    RPM_WITH_NON_ASCII_URL,
    SMALL_COMPS_XML,
    SMALL_CATEGORY,
    SMALL_ENVIRONMENTS,
    SMALL_GROUPS,
    SMALL_LANGPACK,
)

SMALL_CONTENT = SMALL_GROUPS + SMALL_CATEGORY + SMALL_LANGPACK + SMALL_ENVIRONMENTS
CENTOS8_CONTENT = BIG_GROUPS + BIG_CATEGORY + BIG_LANGPACK + BIG_ENVIRONMENTS


def test_single_request_unit_and_duplicate_unit(
    delete_orphans_pre, rpm_package_api, monitor_task, pulpcore_bindings
):
    """Test single request upload unit.

    1. Upload a unit
    2. Attempt to upload same unit
    """
    # Single unit upload
    file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)

    labels = {"key_1": "value_1"}
    with NamedTemporaryFile() as file_to_upload:
        file_to_upload.write(requests.get(file_to_use).content)
        upload_attrs = {"file": file_to_upload.name, "pulp_labels": labels}
        upload = rpm_package_api.create(**upload_attrs)

    content = monitor_task(upload.task).created_resources[0]
    package = rpm_package_api.read(content)
    assert package.location_href == RPM_PACKAGE_FILENAME
    assert package.pulp_labels == labels

    # Duplicate unit
    with NamedTemporaryFile() as file_to_upload:
        file_to_upload.write(requests.get(file_to_use).content)
        upload_attrs = {"file": file_to_upload.name}
        upload = rpm_package_api.create(**upload_attrs)

    try:
        monitor_task(upload.task)
    except PulpTaskError:
        pass
    task_report = pulpcore_bindings.TasksApi.read(upload.task)
    assert task_report.created_resources[0] == package.pulp_href


def test_upload_non_ascii(delete_orphans_pre, rpm_package_api, monitor_task):
    """Test whether one can upload an RPM with non-ascii metadata."""
    packages_count = rpm_package_api.list().count
    with NamedTemporaryFile() as file_to_upload:
        file_to_upload.write(requests.get(RPM_WITH_NON_ASCII_URL).content)
        upload_attrs = {"file": file_to_upload.name}
        upload = rpm_package_api.create(**upload_attrs)

    monitor_task(upload.task)
    new_packages_count = rpm_package_api.list().count
    assert (packages_count + 1) == new_packages_count


@pytest.fixture
def upload_comps_into(rpm_comps_api, monitor_task):
    def _upload_comps_into(file_path, expected_totals, repo_href=None, replace=False):
        data = {}
        if repo_href:
            data["repository"] = repo_href
            data["replace"] = replace
            expected_totals += 1
        response = rpm_comps_api.rpm_comps_upload(file=file_path, **data)
        task = monitor_task(response.task)
        rsrcs = task.created_resources
        assert expected_totals == len(rsrcs)
        return rsrcs

    return _upload_comps_into


def test_upload_comps_xml(delete_orphans_pre, upload_comps_into):
    """Upload a comps.xml and make sure it created comps-Content."""
    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(SMALL_COMPS_XML)
        comps_file.flush()
        resources = upload_comps_into(comps_file.name, SMALL_CONTENT)
    eval_resources(resources)


def test_upload_same_comps_xml(delete_orphans_pre, upload_comps_into):
    """Upload a comps.xml twice and make sure it doesn't create new objects the second time."""
    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(SMALL_COMPS_XML)
        comps_file.flush()
        first = upload_comps_into(comps_file.name, SMALL_CONTENT)
        second = upload_comps_into(comps_file.name, SMALL_CONTENT)

    # we return all resources in the comps.xml, even if they already existed
    assert sorted(first) == sorted(second)


def test_upload_diff_comps_xml(delete_orphans_pre, upload_comps_into):
    """Upload two different comps-files and make sure the second shows the new comps-Content."""
    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(SMALL_COMPS_XML)
        comps_file.flush()
        upload_comps_into(comps_file.name, SMALL_CONTENT)
    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(BIG_COMPS_XML)
        comps_file.flush()
        second = upload_comps_into(comps_file.name, CENTOS8_CONTENT)
    eval_resources(second, is_small=False)


def test_upload_comps_xml_into_repo(
    delete_orphans_pre, rpm_repository_factory, rpm_repository_version_api, upload_comps_into
):
    """Upload comps into a repo and see new version created containing the comps-Content."""
    repo = rpm_repository_factory()

    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(SMALL_COMPS_XML)
        comps_file.flush()
        resources = upload_comps_into(comps_file.name, SMALL_CONTENT, repo.pulp_href)

    vers = [g for g in resources if "versions" in g]
    assert len(vers) == 1
    vers_resp = rpm_repository_version_api.read(vers[0])
    assert len(vers_resp.content_summary.added) == 3
    assert len(vers_resp.content_summary.present) == 3
    eval_counts(vers_resp.content_summary.added)


def test_upload_comps_xml_into_repo_add(
    delete_orphans_pre, rpm_repository_factory, rpm_repository_version_api, upload_comps_into
):
    """Upload two comps-files into a repo and see the result being additive."""
    repo = rpm_repository_factory()

    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(SMALL_COMPS_XML)
        comps_file.flush()
        resources = upload_comps_into(comps_file.name, SMALL_CONTENT, repo.pulp_href)

    vers = [g for g in resources if "versions" in g]
    assert len(vers) == 1
    vers_resp = rpm_repository_version_api.read(vers[0])
    assert len(vers_resp.content_summary.added) == 3
    assert len(vers_resp.content_summary.present) == 3

    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(BIG_COMPS_XML)
        comps_file.flush()
        resources = upload_comps_into(comps_file.name, CENTOS8_CONTENT, repo.pulp_href)
    vers = [g for g in resources if "versions" in g]
    assert len(vers) == 1
    vers_resp = rpm_repository_version_api.read(vers[0])
    assert vers_resp.number == 2

    assert len(vers_resp.content_summary.added) == 3
    assert len(vers_resp.content_summary.present) == 4
    eval_counts(vers_resp.content_summary.added, is_small=False)
    eval_sum_counts(vers_resp.content_summary.present)


def test_upload_comps_xml_into_repo_replace(
    delete_orphans_pre, rpm_repository_factory, rpm_repository_version_api, upload_comps_into
):
    """Upload two comps, see the comps-content from the second replace the existing."""
    repo = rpm_repository_factory()

    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(SMALL_COMPS_XML)
        comps_file.flush()
        upload_comps_into(comps_file.name, SMALL_CONTENT, repo.pulp_href)
    with NamedTemporaryFile("w+") as comps_file:
        comps_file.write(BIG_COMPS_XML)
        comps_file.flush()
        resources = upload_comps_into(comps_file.name, CENTOS8_CONTENT, repo.pulp_href, True)
    vers = [g for g in resources if "versions" in g]
    assert len(vers) == 1
    vers_resp = rpm_repository_version_api.read(vers[0])
    assert vers_resp.number == 2

    assert len(vers_resp.content_summary.added) == 3
    assert len(vers_resp.content_summary.present) == 3
    eval_counts(vers_resp.content_summary.added, is_small=False)


def test_synchronous_package_upload(delete_orphans_pre, rpm_package_api, gen_user):
    """Test synchronously uploading an RPM.

    1. Upload a unit
    2. Attempt to upload same unit with different labels
    3. Assert that labels don't change.
    """
    # Single unit upload
    file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)

    with gen_user(model_roles=["rpm.rpm_package_uploader"]):
        labels = {"key_1": "value_1"}
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(requests.get(file_to_use).content)
            upload_attrs = {"file": file_to_upload.name, "pulp_labels": labels}
            package = rpm_package_api.upload(**upload_attrs)

        assert package.location_href == RPM_PACKAGE_FILENAME
        assert package.pulp_labels == labels

        # Duplicate unit
        with NamedTemporaryFile() as file_to_upload:
            new_labels = {"key_2": "value_2"}
            file_to_upload.write(requests.get(file_to_use).content)
            upload_attrs = {"file": file_to_upload.name, "pulp_labels": new_labels}
            duplicate_package = rpm_package_api.upload(**upload_attrs)

        assert duplicate_package.pulp_href == package.pulp_href
        assert duplicate_package.pulp_labels == package.pulp_labels
        assert duplicate_package.pulp_labels != new_labels

    with gen_user(model_roles=[]), pytest.raises(ApiException) as ctx:
        labels = {"key_1": "value_1"}
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(requests.get(file_to_use).content)
            upload_attrs = {"file": file_to_upload.name, "pulp_labels": labels}
            rpm_package_api.upload(**upload_attrs)
    assert ctx.value.status == 403


def test_synchronous_package_upload_from_artifact(rpm_package_api, gen_user, pulpcore_bindings):
    """Test synchronously uploading an RPM.

    1. Create an Artifact from an RPM, if it doesn't exist.
    2. Use synchronous RPM upload API with an Artifact.
    3. Assert that the RPM package created has a matching artifact.
    """
    file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME2)
    with NamedTemporaryFile() as file_to_upload:
        file_to_upload.write(requests.get(file_to_use).content)
        try:
            artifact = pulpcore_bindings.ArtifactsApi.create(file_to_upload.name)
        except BadRequestException as exc:
            sha256sum = exc.body.split("'")[1]
            artifact = pulpcore_bindings.ArtifactsApi.list(sha256=sha256sum).results[0]

    with gen_user(model_roles=["rpm.rpm_package_uploader"]):
        # Using an existing artifact
        upload_attrs = {"artifact": artifact.pulp_href}
        package_from_artifact = rpm_package_api.upload(**upload_attrs)
    assert package_from_artifact.artifact == artifact.pulp_href


def test_synchronous_package_upload_from_chunks(
    delete_orphans_pre, rpm_package_api, gen_user, pulpcore_bindings, tmp_path
):
    """Test synchronously uploading an RPM using chunked upload.

    1. Upload an RPM file in chunks.
    2. Use synchronous RPM upload API with the upload object.
    3. Assert that the RPM package is created successfully.
    """
    import hashlib
    import uuid

    file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)

    # Download the file and prepare chunks
    with NamedTemporaryFile(delete=False) as file_to_upload:
        file_to_upload.write(requests.get(file_to_use).content)
        file_to_upload.flush()
        file_path = file_to_upload.name

    # Create chunks (similar to pulpcore_chunked_file_factory)
    chunk_size = 512
    chunks = []
    hasher = hashlib.new("sha256")

    with open(file_path, "rb") as f:
        data = f.read()

    file_size = len(data)
    start = 0

    while start < len(data):
        content = data[start : start + chunk_size]
        chunk_file = tmp_path / str(uuid.uuid4())
        hasher.update(content)
        chunk_file.write_bytes(content)
        content_sha = hashlib.sha256(content).hexdigest()
        end = start + len(content) - 1
        chunks.append((str(chunk_file), f"bytes {start}-{end}/{file_size}", content_sha))
        start += len(content)

    # Create an Upload object (requires core permissions, done outside gen_user)
    upload = pulpcore_bindings.UploadsApi.create({"size": file_size})

    # Upload all chunks
    for chunk_file, content_range, chunk_sha in chunks:
        pulpcore_bindings.UploadsApi.update(
            upload_href=upload.pulp_href,
            file=chunk_file,
            content_range=content_range,
            sha256=chunk_sha,
        )

    # Use synchronous upload API with the upload object (requires rpm uploader role)
    with gen_user(model_roles=["rpm.rpm_package_uploader"]):
        upload_attrs = {"upload": upload.pulp_href}
        package = rpm_package_api.upload(**upload_attrs)

        # Verify package was created successfully
        assert package.location_href == RPM_PACKAGE_FILENAME

    # Clean up
    os.unlink(file_path)


def eval_resources(resources, is_small=True):
    """Eval created_resources counts."""
    groups = [g for g in resources if "packagegroups" in g]
    assert len(groups) == (SMALL_GROUPS if is_small else BIG_GROUPS)

    categories = [g for g in resources if "packagecategories" in g]
    assert len(categories) == (SMALL_CATEGORY if is_small else BIG_CATEGORY)

    langpacks = [g for g in resources if "packagelangpacks" in g]
    assert len(langpacks) == (SMALL_LANGPACK if is_small else BIG_LANGPACK)

    envs = [g for g in resources if "environment" in g]
    assert len(envs) == (SMALL_ENVIRONMENTS if is_small else BIG_ENVIRONMENTS)


def eval_counts(summary, is_small=True):
    """Eval counts in a given summary."""
    for c in summary:
        if "rpm.packagegroup" in c:
            count = SMALL_GROUPS if is_small else BIG_GROUPS
            assert summary["rpm.packagegroup"]["count"] == count
        elif "rpm.packageenvironment" in c:
            count = SMALL_ENVIRONMENTS if is_small else BIG_ENVIRONMENTS
            assert summary["rpm.packageenvironment"]["count"] == count
        elif RPM_PACKAGECATEGORY_CONTENT_NAME in c:
            count = SMALL_CATEGORY if is_small else BIG_CATEGORY
            assert summary[RPM_PACKAGECATEGORY_CONTENT_NAME]["count"] == count
        elif "rpm.packagelangpacks" in c:
            count = SMALL_LANGPACK if is_small else BIG_LANGPACK
            assert summary["rpm.packagelangpacks"]["count"] == count


def eval_sum_counts(summary):
    """In a given summary, counts should be BIG+SMALL."""
    for c in summary:
        if RPM_PACKAGEGROUP_CONTENT_NAME in c:
            count = BIG_GROUPS + SMALL_GROUPS
            assert summary[RPM_PACKAGEGROUP_CONTENT_NAME]["count"] == count
        elif RPM_PACKAGEENVIRONMENT_CONTENT_NAME in c:
            count = BIG_ENVIRONMENTS + SMALL_ENVIRONMENTS
            assert summary[RPM_PACKAGEENVIRONMENT_CONTENT_NAME]["count"] == count
        elif RPM_PACKAGECATEGORY_CONTENT_NAME in c:
            count = BIG_CATEGORY + SMALL_CATEGORY
            assert summary[RPM_PACKAGECATEGORY_CONTENT_NAME]["count"] == count
        elif RPM_PACKAGELANGPACKS_CONTENT_NAME in c:
            count = BIG_LANGPACK + SMALL_LANGPACK
            assert summary[RPM_PACKAGELANGPACKS_CONTENT_NAME]["count"] == count
