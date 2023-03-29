"""Tests for Pulp's characters encoding."""
import pytest
import uuid

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_rpm.tests.functional.constants import (
    RPM_WITH_NON_ASCII_NAME,
    RPM_WITH_NON_ASCII_URL,
    RPM_WITH_NON_UTF_8_NAME,
    RPM_WITH_NON_UTF_8_URL,
)


"""Test upload of RPMs with different character encoding.

This test targets the following issues:

* `Pulp #4210 <https://pulp.plan.io/issues/4210>`_
* `Pulp #4215 <https://pulp.plan.io/issues/4215>`_
"""


def test_upload_non_ascii(
    tmp_path, artifacts_api_client, http_get, rpm_package_api, monitor_task, delete_orphans_pre
):
    """Test whether one can upload an RPM with non-ascii metadata."""
    temp_file = tmp_path / str(uuid.uuid4())
    temp_file.write_bytes(http_get(RPM_WITH_NON_ASCII_URL))
    artifact = artifacts_api_client.create(temp_file)
    response = rpm_package_api.create(
        artifact=artifact.pulp_href,
        relative_path=RPM_WITH_NON_ASCII_NAME,
    )
    task = monitor_task(response.task)
    assert len(task.created_resources) == 1


def test_upload_non_utf8(
    tmp_path, artifacts_api_client, http_get, rpm_package_api, monitor_task, delete_orphans_pre
):
    """Test whether an exception is raised when non-utf-8 is uploaded."""
    temp_file = tmp_path / str(uuid.uuid4())
    temp_file.write_bytes(http_get(RPM_WITH_NON_UTF_8_URL))
    artifact = artifacts_api_client.create(temp_file)
    with pytest.raises(PulpTaskError) as ctx:
        response = rpm_package_api.create(
            artifact=artifact.pulp_href,
            relative_path=RPM_WITH_NON_UTF_8_NAME,
        )
        monitor_task(response.task)

    assert "'utf-8' codec can't decode byte 0x80 in position 168: invalid start" in str(ctx.value)
