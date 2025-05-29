"""Tests that sync rpm plugin repositories."""

import pytest
import os
from datetime import datetime

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_REPOMETADATA,
    RHEL8_APPSTREAM_CDN_URL,
    RHEL8_BASEOS_CDN_URL,
    RPM_KICKSTART_CONTENT_NAME,
    RPM_KICKSTART_COUNT,
    CENTOS8_STREAM_APPSTREAM_URL,
    CENTOS8_STREAM_BASEOS_URL,
    CENTOS10_STREAM_APPSTREAM_URL,
    CENTOS10_STREAM_BASEOS_URL,
    EPEL8_MIRRORLIST_URL,
    RAWHIDE_KICKSTART_URL,
)


def parse_date_from_string(s, parse_format="%Y-%m-%dT%H:%M:%S.%fZ"):
    """Parse string to datetime object.

    :param s: str like '2018-11-18T21:03:32.493697Z'
    :param parse_format: str defaults to %Y-%m-%dT%H:%M:%S.%fZ
    :return: datetime.datetime
    """
    if isinstance(s, datetime):
        return s
    else:
        return datetime.strptime(s, parse_format)


@pytest.mark.parametrize(
    "url,policy,check_dist_tree,resync",
    [
        pytest.param(
            CENTOS8_STREAM_BASEOS_URL,
            "immediate",
            True,
            True,
            marks=pytest.mark.skip("Skip to avoid failing due to running out of disk space"),
        ),
        (CENTOS8_STREAM_BASEOS_URL, "on_demand", True, True),
        (CENTOS8_STREAM_APPSTREAM_URL, "on_demand", True, True),
        (EPEL8_MIRRORLIST_URL, "on_demand", False, False),
        (RAWHIDE_KICKSTART_URL, "on_demand", True, True),
        (CENTOS10_STREAM_BASEOS_URL, "on_demand", True, True),
        (CENTOS10_STREAM_APPSTREAM_URL, "on_demand", True, True),
    ],
)
def test_rpm_sync(
    url,
    policy,
    check_dist_tree,
    resync,
    init_and_sync,
    rpm_repository_version_api,
    delete_orphans_pre,
):
    """Sync repositories with the rpm plugin."""
    # Create repository & remote and sync
    repo, remote, task = init_and_sync(url=url, policy=policy, return_task=True)

    created_at = parse_date_from_string(task.pulp_created)
    started_at = parse_date_from_string(task.started_at)
    finished_at = parse_date_from_string(task.finished_at)
    task_duration = finished_at - started_at
    waiting_time = started_at - created_at
    print(
        "\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(), service=task_duration.total_seconds()
        )
    )

    # Check that we have the correct content counts.
    if check_dist_tree:
        repo_ver = rpm_repository_version_api.read(repo.latest_version_href)
        present_summary = repo_ver.content_summary.present
        assert RPM_KICKSTART_CONTENT_NAME in present_summary
        assert present_summary[RPM_KICKSTART_CONTENT_NAME]["count"] == RPM_KICKSTART_COUNT
        added_summary = repo_ver.content_summary.added
        assert RPM_KICKSTART_CONTENT_NAME in added_summary
        assert added_summary[RPM_KICKSTART_CONTENT_NAME]["count"] == RPM_KICKSTART_COUNT

    if resync:
        # Sync the repository again.
        latest_version_href = repo.latest_version_href
        repo, remote, task = init_and_sync(repository=repo, remote=remote, return_task=True)
        created_at = parse_date_from_string(task.pulp_created)
        started_at = parse_date_from_string(task.started_at)
        finished_at = parse_date_from_string(task.finished_at)
        task_duration = finished_at - started_at
        waiting_time = started_at - created_at
        print(
            "\n->  Re-sync => Waiting time (s): {wait} | Service time (s): {service}".format(
                wait=waiting_time.total_seconds(), service=task_duration.total_seconds()
            )
        )

        # Check that nothing has changed since the last sync.
        assert latest_version_href == repo.latest_version_href


@pytest.fixture
def cdn_certs_and_keys():
    cdn_client_cert = os.getenv("CDN_CLIENT_CERT", "").replace("\\n", "\n")
    cdn_client_key = os.getenv("CDN_CLIENT_KEY", "").replace("\\n", "\n")
    cdn_ca_cert = os.getenv("CDN_CA_CERT", "").replace("\\n", "\n")

    return cdn_client_cert, cdn_client_key, cdn_ca_cert


def test_sync_with_certificate(
    cdn_certs_and_keys,
    init_and_sync,
    rpm_rpmremote_factory,
    rpm_content_repometadata_files_api,
    rpm_repository_version_api,
    delete_orphans_pre,
):
    """Test sync against CDN.

    1. create repository, appstream remote and sync
        - remote using certificates and tls validation
    2. create repository, baseos remote and sync
        - remote using certificates without tls validation
    3. Check both repositories were synced and both have its own 'productid' content
        - this test covering checking same repo metadata files with different relative paths
    """
    client_cert, client_key, ca_cert = cdn_certs_and_keys
    if not all(cdn_certs_and_keys):
        pytest.skip("CDN Client Cert & Key and CA Cert were not set")

    # 1. create repo, remote and sync them
    appstream_remote = rpm_rpmremote_factory(
        url=RHEL8_APPSTREAM_CDN_URL,
        client_cert=client_cert,
        client_key=client_key,
        ca_cert=ca_cert,
        policy="on_demand",
    )
    repo_appstream, _ = init_and_sync(remote=appstream_remote)

    # 2. create remote and re-sync
    baseos_remote = rpm_rpmremote_factory(
        url=RHEL8_BASEOS_CDN_URL,
        tls_validation=False,
        client_cert=client_cert,
        client_key=client_key,
        policy="on_demand",
    )
    repo_baseos, _ = init_and_sync(remote=baseos_remote)

    # Get all 'productid' repo metadata files
    productids = [
        productid
        for productid in rpm_content_repometadata_files_api.list().results
        if productid.data_type == "productid"
    ]

    # Assert there are two productid content units and they have same checksum
    assert len(productids) == 2
    assert productids[0].checksum == productids[1].checksum

    # Assert each repository has its own productid file
    appstream_repo_ver = rpm_repository_version_api.read(repo_appstream.latest_version_href)
    assert appstream_repo_ver.content_summary.present[PULP_TYPE_REPOMETADATA]["count"] == 1
    baseos_repo_ver = rpm_repository_version_api.read(repo_baseos.latest_version_href)
    assert baseos_repo_ver.content_summary.present[PULP_TYPE_REPOMETADATA]["count"] == 1

    appstream_metadata = rpm_content_repometadata_files_api.list(
        repository_version=appstream_repo_ver.pulp_href
    )
    baseos_metadata = rpm_content_repometadata_files_api.list(
        repository_version=baseos_repo_ver.pulp_href
    )
    assert appstream_metadata.results[0].relative_path != baseos_metadata.results[0].relative_path
