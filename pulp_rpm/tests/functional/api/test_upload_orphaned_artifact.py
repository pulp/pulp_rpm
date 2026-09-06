"""Regression test for https://github.com/pulp/pulp_rpm/issues/4574

RPM upload must return a 4xx error (not 500) when the artifact file exists
in storage but the corresponding Artifact database record is absent.
"""

import hashlib
import shutil
from pathlib import Path

import pytest

from pulpcore.client.pulp_rpm import ApiException

from pulp_rpm.tests.shared_utils import Nevra, build_rpm


def test_upload_returns_client_error_when_artifact_file_exists_without_db_record(
    delete_orphans_pre, rpm_package_api, pulpcore_bindings, tmp_path
):
    """RPM upload returns 4xx (not 500) when the artifact file is in storage with no DB record.

    The inconsistent state is created by:
    1. Uploading an RPM as a bare artifact so its file lands in artifact storage.
    2. Deleting the artifact via the API, which removes the DB record and the file.
    3. Copying the file back to the storage path, leaving storage inconsistent.
    4. Uploading the same RPM as a package — this triggers the orphaned-artifact code path.
    """
    rpm_file = tmp_path / "test-upload-orphan.rpm"
    build_rpm(Nevra("test-upload-orphan", 0, "1.0", "1", "noarch"), rpm_file)

    sha256 = hashlib.sha256(rpm_file.read_bytes()).hexdigest()
    artifact_storage_path = Path(f"/var/lib/pulp/media/artifact/{sha256[:2]}/{sha256[2:]}")

    # Upload the RPM as a bare artifact so the file is placed in artifact storage.
    artifact = pulpcore_bindings.ArtifactsApi.create(file=str(rpm_file))
    assert artifact.sha256 == sha256

    backup_path = tmp_path / "artifact.backup"
    shutil.copy2(str(artifact_storage_path), str(backup_path))

    # Delete the artifact — removes both the DB record and the file from storage.
    pulpcore_bindings.ArtifactsApi.delete(artifact.pulp_href)
    assert not artifact_storage_path.exists()

    # Restore the file to storage, creating the inconsistent state (file on disk, no DB record).
    artifact_storage_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(backup_path), str(artifact_storage_path))

    # The upload must NOT return HTTP 500.
    # Before the fix, an unhandled ValueError propagated through DRF and produced a 500.
    with pytest.raises(ApiException) as exc_info:
        rpm_package_api.create(file=str(rpm_file))

    assert exc_info.value.status != 500, (
        f"Upload returned HTTP 500 instead of a proper 4xx error: {exc_info.value.body}"
    )
    assert 400 <= exc_info.value.status < 500, (
        f"Expected a 4xx client error but got HTTP {exc_info.value.status}"
    )
