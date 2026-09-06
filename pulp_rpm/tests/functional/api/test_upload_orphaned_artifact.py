"""Regression test for https://github.com/pulp/pulp_rpm/issues/4574

RPM upload must return a 4xx error (not 500) when the artifact file exists
in storage but the corresponding Artifact database record is absent.
"""

import hashlib
import os
from pathlib import Path

import pytest
import requests

from pulp_rpm.tests.functional.utils import Nevra, build_rpm


def _api_url(path: str) -> str:
    """Build an API URL compatible with both pulp-service and upstream-mode containers.

    pulp-service: API_ROOT=/api/pulp/  → http://host/api/pulp/default/api/v3/<path>
    upstream:     API_ROOT=/pulp/      → http://host/pulp/api/v3/<path>
    """
    protocol = os.environ.get("API_PROTOCOL", "https")
    host = os.environ.get("API_HOST", "localhost")
    port = os.environ.get("API_PORT", "443")
    base = f"{protocol}://{host}:{port}"
    try:
        from django.conf import settings
        api_root = getattr(settings, "API_ROOT", "/pulp/")
        # pulp-service uses domain-scoped URLs: {API_ROOT}{domain}/api/v3/
        # upstream uses: {API_ROOT}api/v3/
        if api_root != "/pulp/":
            domain = getattr(settings, "DEFAULT_DOMAIN_NAME", "default")
            return f"{base}{api_root}{domain}/api/v3/{path}"
    except Exception:
        pass
    return f"{base}/pulp/api/v3/{path}"


def test_upload_returns_client_error_when_artifact_file_exists_without_db_record(
    tmp_path
):
    """RPM upload returns 4xx (not 500) when the artifact file is in storage with no DB record.

    The inconsistent state is created by pre-placing the RPM file at its expected artifact
    storage path (based on sha256) without creating a database record for it.  This is the
    real-world state left behind when a previous upload process is interrupted after the file
    is moved to artifact storage but before the database transaction commits.

    Uploading the same RPM then triggers the orphaned-artifact code path in the serializer.
    """
    rpm_file = tmp_path / "test-upload-orphan.rpm"
    build_rpm(Nevra("test-upload-orphan", 0, "1.0", "1", "noarch"), rpm_file)

    sha256 = hashlib.sha256(rpm_file.read_bytes()).hexdigest()

    # Determine the artifact storage path from Django settings.
    try:
        from django.conf import settings
        media_root = Path(settings.MEDIA_ROOT)
    except Exception:
        media_root = Path("/var/lib/pulp/media")
    artifact_storage_path = media_root / "artifact" / sha256[:2] / sha256[2:]

    # Pre-place the file in artifact storage with no corresponding DB record.
    # This mimics an interrupted upload that moved the file but never committed the transaction.
    artifact_storage_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_storage_path.write_bytes(rpm_file.read_bytes())

    auth = (
        os.environ.get("ADMIN_USERNAME", "admin"),
        os.environ.get("ADMIN_PASSWORD", "password"),
    )
    url = _api_url(f"content/rpm/packages/")

    # The upload must NOT return HTTP 500.
    # Before the fix, an unhandled ValueError propagated through DRF and produced a 500.
    with open(rpm_file, "rb") as fh:
        response = requests.post(url, auth=auth, files={"file": fh})

    assert response.status_code != 500, (
        f"Upload returned HTTP 500 instead of a proper 4xx error: {response.text[:500]}"
    )
    assert 400 <= response.status_code < 500, (
        f"Expected a 4xx client error but got HTTP {response.status_code}: {response.text[:200]}"
    )
