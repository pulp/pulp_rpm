"""Tests that sync rpm plugin repositories."""
import pytest
from random import choice

import dictdiffer
from django.conf import settings
from django.utils.dateparse import parse_datetime

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_added_content,
    get_content,
    get_content_summary,
    get_removed_content,
    wget_download_on_host,
)

from pulp_rpm.tests.functional.constants import (
    AMAZON_MIRROR,
    CENTOS7_OPSTOOLS_URL,
    PULP_TYPE_ADVISORY,
    PULP_TYPE_MODULEMD,
    PULP_TYPE_PACKAGE,
    PULP_TYPE_REPOMETADATA,
    REPO_WITH_XML_BASE_URL,
    RPM_ADVISORY_CONTENT_NAME,
    RPM_ADVISORY_COUNT,
    RPM_ADVISORY_DIFFERENT_PKGLIST_URL,
    RPM_ADVISORY_DIFFERENT_REPO_URL,
    RPM_ADVISORY_INCOMPLETE_PKG_LIST_URL,
    RPM_ADVISORY_NO_UPDATED_DATE,
    RPM_ADVISORY_TEST_ADDED_COUNT,
    RPM_ADVISORY_TEST_ID,
    RPM_ADVISORY_TEST_ID_NEW,
    RPM_ADVISORY_TEST_REMOVE_COUNT,
    RPM_ADVISORY_UPDATED_VERSION_URL,
    RPM_CUSTOM_REPO_METADATA_CHANGED_FIXTURE_URL,
    RPM_CUSTOM_REPO_METADATA_FIXTURE_URL,
    RPM_EPEL_MIRROR_URL,
    RPM_COMPLEX_FIXTURE_URL,
    RPM_COMPLEX_PACKAGE_DATA,
    RPM_FIXTURE_SUMMARY,
    RPM_INVALID_FIXTURE_URL,
    RPM_KICKSTART_DATA,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_MD5_REPO_FIXTURE_URL,
    RPM_MIRROR_LIST_BAD_FIXTURE_URL,
    RPM_MIRROR_LIST_GOOD_FIXTURE_URL,
    RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_SUMMARY,
    RPM_MODULAR_FIXTURE_URL,
    RPM_MODULAR_STATIC_FIXTURE_SUMMARY,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_PACKAGE_COUNT,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_SHA_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
    RPM_SIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_UPDATED_UPDATEINFO_FIXTURE_URL,
    SRPM_UNSIGNED_FIXTURE_ADVISORY_COUNT,
    SRPM_UNSIGNED_FIXTURE_PACKAGE_COUNT,
    SRPM_UNSIGNED_FIXTURE_URL,
    RPM_MODULEMD_DEFAULTS_DATA,
    RPM_MODULEMD_OBSOLETES_DATA,
    RPM_MODULEMDS_DATA,
    RPM_ZSTD_METADATA_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL
from pulpcore.client.pulp_rpm.exceptions import ApiException


@pytest.mark.parallel
def test_sync(init_and_sync):
    """Sync repositories with the rpm plugin."""
    # Create a remote (default) and empty repository
    repository, remote = init_and_sync()

    # Assert that it's synced properly
    latest_version_href = repository.latest_version_href
    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY

    # Sync the same repository again
    repository, _ = init_and_sync(repository=repository, remote=remote)

    # Assert that the repository has not changed, the latest version stays the same
    assert latest_version_href == repository.latest_version_href
    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY


@pytest.mark.parallel
def test_sync_zstd(init_and_sync):
    """Test syncing non-gzip metadata."""
    repository, _ = init_and_sync(url=RPM_ZSTD_METADATA_FIXTURE_URL)

    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY


@pytest.mark.parallel
def test_sync_local(init_and_sync, tmpdir):
    """Test syncing from the local filesystem."""
    wget_download_on_host(RPM_UNSIGNED_FIXTURE_URL, str(tmpdir))
    init_and_sync(url=f"file://{tmpdir}/rpm-unsigned/")


@pytest.mark.parallel
def test_sync_from_valid_mirror_list_feed(init_and_sync):
    """Sync RPM content from a mirror list feed which contains a valid remote URL."""
    repository, _ = init_and_sync(url=RPM_MIRROR_LIST_GOOD_FIXTURE_URL)

    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY


@pytest.mark.parallel
def test_sync_from_valid_mirror_list_feed_with_params(init_and_sync):
    """Sync RPM content from a mirror list feed which contains a valid remote URL."""
    init_and_sync(url=RPM_EPEL_MIRROR_URL)


@pytest.mark.parallel
def test_sync_from_invalid_mirror_list_feed(init_and_sync):
    """Sync RPM content from a mirror list feed which contains an invalid remote URL."""
    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(url=RPM_MIRROR_LIST_BAD_FIXTURE_URL)

    assert "An invalid remote URL was provided" in exc.value.task.to_dict()["error"]["description"]


@pytest.mark.parallel
def test_sync_modular(init_and_sync):
    """Sync RPM modular content."""
    repository, _ = init_and_sync(url=RPM_MODULAR_FIXTURE_URL)

    assert get_content_summary(repository.to_dict()) == RPM_MODULAR_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_MODULAR_FIXTURE_SUMMARY


@pytest.mark.parallel
def test_checksum_constraint(init_and_sync):
    """Verify checksum constraint test case.

    Do the following:

    1. Create and sync a repo using the following
       url=RPM_REFERENCES_UPDATEINFO_URL.
    2. Create and sync a secondary repo using the following
       url=RPM_UNSIGNED_FIXTURE_URL.
       Those urls have RPM packages with the same name.
    3. Assert that the task succeed.
    """
    for url in [RPM_REFERENCES_UPDATEINFO_URL, RPM_UNSIGNED_FIXTURE_URL]:
        repository, _ = init_and_sync(url=url)

        assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
        assert get_added_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY


@pytest.mark.parallel
@pytest.mark.parametrize("policy", ["on_demand", "immediate"])
def test_kickstart(policy, init_and_sync, rpm_content_distribution_trees_api):
    """Sync repositories with the rpm plugin.

    Do the following:

    1. Create a remote.
    2. Sync the remote.
    3. Assert that the correct number of units were added and are present
       in the repo.
    4. Sync the remote one more time.
    5. Assert that repository version is the same the previous one.
    6. Assert that the same number of packages are present.
    """
    repository, remote = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL, policy=policy)

    latest_version_href = repository.latest_version_href
    assert get_content_summary(repository.to_dict()) == RPM_KICKSTART_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_KICKSTART_FIXTURE_SUMMARY

    repository, _ = init_and_sync(repository=repository, remote=remote)

    assert get_content_summary(repository.to_dict()) == RPM_KICKSTART_FIXTURE_SUMMARY
    assert latest_version_href == repository.latest_version_href

    distribution_tree = rpm_content_distribution_trees_api.list(
        repository_version=latest_version_href
    ).results[0]
    assert "RHEL" == distribution_tree.release_short


def test_mutated_packages(init_and_sync):
    """Sync two copies of the same packages.

    Make sure we end up with only one copy.

    Do the following:

    1. Sync.
    3. Assert that the content summary matches what is expected.
    4. Create a new remote w/ using fixture containing updated advisory
       (packages with the same NEVRA as the existing package content, but
       different pkgId).
    5. Sync the remote again.
    6. Assert that repository version is different from the previous one
       but has the same content summary.
    7. Assert that the packages have changed since the last sync.
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)

    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY

    # Save the copy of the original packages.
    original_packages = {
        (
            content["name"],
            content["epoch"],
            content["version"],
            content["release"],
            content["arch"],
        ): content
        for content in get_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME]
    }

    # Create a remote with a different test fixture with the same NEVRA but
    # different digests.
    repository, _ = init_and_sync(repository=repository, url=RPM_SIGNED_FIXTURE_URL)

    # In case of "duplicates" the most recent one is chosen, so the old
    # package is removed from and the new one is added to a repo version.
    assert (
        len(get_added_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME])
    ) == RPM_PACKAGE_COUNT
    assert (
        len(get_removed_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME])
    ) == RPM_PACKAGE_COUNT

    # Test that the packages have been modified.
    mutated_packages = {
        (
            content["name"],
            content["epoch"],
            content["version"],
            content["release"],
            content["arch"],
        ): content
        for content in get_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME]
    }

    for nevra in original_packages:
        assert original_packages[nevra]["pkgId"] != mutated_packages[nevra]["pkgId"]


def test_sync_diff_checksum_packages(init_and_sync):
    """Sync two fixture content with same NEVRA and different checksum.

    Make sure we end up with the most recently synced content.

    Do the following:

    1. Create two remotes with same content but different checksums.
        Sync the remotes one after the other.
           a. Sync remote with packages with SHA256: ``RPM_UNSIGNED_FIXTURE_URL``.
           b. Sync remote with packages with SHA512: ``RPM_SHA512_FIXTURE_URL``.
    2. Make sure the latest content is only kept.
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")

    repository, _ = init_and_sync(repository=repository, url=RPM_SHA512_FIXTURE_URL)

    added_content = get_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME]
    removed_content = get_removed_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME]

    # In case of "duplicates" the most recent one is chosen, so the old
    # package is removed from and the new one is added to a repo version.
    assert len(added_content) == RPM_PACKAGE_COUNT
    assert len(removed_content) == RPM_PACKAGE_COUNT

    # Verifying whether the packages with first checksum is removed and second
    # is added.
    assert added_content[0]["checksum_type"] == "sha512"
    assert removed_content[0]["checksum_type"] == "sha256"


@pytest.mark.parallel
def test_mutated_advisory_metadata(init_and_sync):
    """Sync two copies of the same Advisory (only description is updated).

    Make sure we end up with only one copy.

    Do the following:

    1. Create a repository and a remote.
    2. Sync the remote.
    3. Assert that the content summary matches what is expected.
    4. Create a new remote w/ using fixture containing updated advisory
       (updaterecords with the ID as the existing updaterecord content, but
       different metadata).
    5. Sync the remote again.
    6. Assert that repository version is different from the previous one
       but has the same content summary.
    7. Assert that the updaterecords have changed since the last sync.
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")

    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert get_added_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY

    original_updaterecords = {
        content["id"]: content
        for content in get_content(repository.to_dict())[RPM_ADVISORY_CONTENT_NAME]
    }

    repository, _ = init_and_sync(repository=repository, url=RPM_UPDATED_UPDATEINFO_FIXTURE_URL)

    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert len(get_added_content(repository.to_dict())[RPM_ADVISORY_CONTENT_NAME]) == 4
    assert len(get_removed_content(repository.to_dict())[RPM_ADVISORY_CONTENT_NAME]) == 4

    # Test that the updateinfo have been modified.
    mutated_updaterecords = {
        content["id"]: content
        for content in get_content(repository.to_dict())[RPM_ADVISORY_CONTENT_NAME]
    }

    assert mutated_updaterecords != original_updaterecords
    assert mutated_updaterecords[RPM_ADVISORY_TEST_ID_NEW]["description"] == (
        "Updated Gorilla_Erratum and the updated date contains timezone"
    )


@pytest.mark.parallel
def test_optimize(
    init_and_sync,
    gen_object_with_cleanup,
    rpm_repository_api,
    rpm_rpmremote_api,
    monitor_task,
):
    """Tests that sync is skipped when no critical parameters of the sync change.

    Sync is forced if:

    * optimize=False
    * sync URL is different from the last sync
    * sync_policy changes to 'mirror_complete' from something else
    * download_policy of the remote is changed to 'immediate' from something else
    * the repository has been modified since the last sync
    * (NOT tested) repomd revision or repomd checksum change
    """
    repository, remote = init_and_sync(policy="on_demand")

    # sync again, assert optimized
    repository_sync_data = RpmRepositorySyncURL(
        remote=remote.pulp_href, sync_policy="mirror_content_only"
    )
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert any(report.code == "sync.was_skipped" for report in task.progress_reports)

    repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, optimize=False)
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert all(report.code != "sync.was_skipped" for report in task.progress_reports)

    # create a new repo version, sync again, assert not optimized
    repository = rpm_repository_api.read(repository.pulp_href)
    content = choice(get_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME])
    response = rpm_repository_api.modify(
        repository.pulp_href, {"remove_content_units": [content["pulp_href"]]}
    )
    monitor_task(response.task)

    repository_sync_data = RpmRepositorySyncURL(
        remote=remote.pulp_href, sync_policy="mirror_content_only"
    )
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert all(report.code != "sync.was_skipped" for report in task.progress_reports)

    # change download policy to 'immediate', sync again, assert not optimized
    body = {"policy": "immediate"}
    monitor_task(rpm_rpmremote_api.partial_update(remote.pulp_href, body).task)

    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert all(report.code != "sync.was_skipped" for report in task.progress_reports)

    # create new remote with the same URL and download_policy as the first and run a sync task
    new_remote = gen_object_with_cleanup(rpm_rpmremote_api, gen_rpm_remote())
    repository_sync_data = RpmRepositorySyncURL(
        remote=new_remote.pulp_href, sync_policy="mirror_content_only"
    )
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert any(report.code == "sync.was_skipped" for report in task.progress_reports)

    # change the URL on the new remote, sync again, assert not optimized
    body = {"url": RPM_RICH_WEAK_FIXTURE_URL}
    monitor_task(rpm_rpmremote_api.partial_update(new_remote.pulp_href, body).task)

    repository_sync_data = RpmRepositorySyncURL(
        remote=new_remote.pulp_href, sync_policy="mirror_content_only"
    )
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert all(report.code != "sync.was_skipped" for report in task.progress_reports)

    # sync again with the new remote, assert optimized
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert any(report.code == "sync.was_skipped" for report in task.progress_reports)

    # sync again with sync_policy='mirror_complete', assert not optimized, but repository
    # version is unchanged
    first_sync_repo_version = rpm_repository_api.read(repository.pulp_href).latest_version_href
    repository_sync_data = RpmRepositorySyncURL(
        remote=new_remote.pulp_href, sync_policy="mirror_complete"
    )
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert all(report.code != "sync.was_skipped" for report in task.progress_reports)

    latest_sync_repo_version = rpm_repository_api.read(repository.pulp_href).latest_version_href

    assert first_sync_repo_version == latest_sync_repo_version

    # sync again with sync_policy='mirror_complete', assert optimized
    sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
    task = monitor_task(sync_response.task)

    assert any(report.code == "sync.was_skipped" for report in task.progress_reports)


@pytest.mark.parallel
def test_sync_advisory_new_version(init_and_sync):
    """Sync a repository and re-sync with newer version of Advisory.

    Test if advisory with same ID and pkglist, but newer version is updated.

    1. Sync rpm-unsigned repository
    2. Re-sync rpm-advisory-updateversion
    3. Check if the newer version advisory was synced
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)

    repository, _ = init_and_sync(repository=repository, url=RPM_ADVISORY_UPDATED_VERSION_URL)

    # check if newer version advisory was added and older removed
    added_advisories = get_added_content(repository.to_dict())[PULP_TYPE_ADVISORY]
    added_advisory = [
        advisory["version"]
        for advisory in added_advisories
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]
    removed_advisories = get_removed_content(repository.to_dict())[PULP_TYPE_ADVISORY]
    removed_advisory = [
        advisory["version"]
        for advisory in removed_advisories
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]
    assert int(added_advisory[0]) > int(removed_advisory[0])


@pytest.mark.parallel
def test_sync_advisory_old_version(init_and_sync):
    """Sync a repository and re-sync with older version of Advisory.

    Test if advisory with same ID and pkglist, but older version is not updated.

    1. Sync rpm-advisory-updateversion
    2. Re-sync rpm-unsigned repository
    3. Check if the newer (already present) version is preserved
    """
    repository, remote = init_and_sync(url=RPM_ADVISORY_UPDATED_VERSION_URL)
    repository_version_old = repository.latest_version_href

    repository, _ = init_and_sync(repository=repository, url=RPM_UNSIGNED_FIXTURE_URL)
    repository_version_new = repository.latest_version_href

    present_advisories = get_content(repository.to_dict())[PULP_TYPE_ADVISORY]
    advisory_version = [
        advisory["version"]
        for advisory in present_advisories
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]

    # check if the newer version is preserved
    assert advisory_version[0] == "2"
    # no new content is present in RPM_UNSIGNED_FIXTURE_URL against
    # RPM_ADVISORY_UPDATED_VERSION_URL so repository latests version should stay the same.
    assert repository_version_old == repository_version_new


@pytest.mark.parallel
def test_sync_merge_advisories(init_and_sync):
    """Sync two advisories with same ID, version and different pkglist.

    Test if two advisories are merged.
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)
    repository, _ = init_and_sync(repository=repository, url=RPM_ADVISORY_DIFFERENT_PKGLIST_URL)

    # check advisories were merged
    added_advisories = get_added_content(repository.to_dict())[PULP_TYPE_ADVISORY]
    added_advisory_pkglist = [
        advisory["pkglist"]
        for advisory in added_advisories
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]
    removed_advisories = get_removed_content(repository.to_dict())[PULP_TYPE_ADVISORY]
    removed_advisory_pkglist = [
        advisory["pkglist"]
        for advisory in removed_advisories
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]
    added_count = 0
    removed_count = 0
    for collection in added_advisory_pkglist[0]:
        added_count += len(collection["packages"])
    for collection in removed_advisory_pkglist[0]:
        removed_count += len(collection["packages"])

    assert RPM_ADVISORY_TEST_REMOVE_COUNT == removed_count
    assert RPM_ADVISORY_TEST_ADDED_COUNT == added_count


@pytest.mark.parallel
def test_sync_advisory_diff_repo(init_and_sync):
    """Test failure sync advisories.

    If advisory has same id, version but different update_date and
    no packages intersection sync should fail.

    Tested error_msg must be same as we use in pulp_rpm.app.advisory.

    NOTE: If ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION is True, this test
    will fail since the errata-merge will be allowed.
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)
    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(repository=repository, url=RPM_ADVISORY_DIFFERENT_REPO_URL)

    error_msg = (
        "Incoming and existing advisories have the same id but "
        "different timestamps and non-intersecting package lists. "
        "It is likely that they are from two different incompatible remote "
        "repositories. E.g. RHELX-repo and RHELY-debuginfo repo. "
        "Ensure that you are adding content for the compatible repositories. "
        "To allow this behavior, set "
        "ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION = True (q.v.) "
        "in your configuration. Advisory id: {}".format(RPM_ADVISORY_TEST_ID)
    )
    assert error_msg in exc.value.task.to_dict()["error"]["description"]


@pytest.mark.parallel
def test_sync_advisory_proper_subset_pgk_list(init_and_sync):
    """Test success: sync advisories where pkglist is proper-subset of another.

    If update_dates and update_version are the same, pkglist intersection is non-empty
    and a proper-subset of the 'other' pkglist, sync should succeed.
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)
    init_and_sync(repository=repository, url=RPM_ADVISORY_INCOMPLETE_PKG_LIST_URL)


@pytest.mark.parallel
def test_sync_advisory_incomplete_pgk_list(init_and_sync):
    """Test failure sync advisories.

    If update_dates and update_version are the same, pkglist intersection is non-empty
    and not equal to either pkglist sync should fail.

    Tested error_msg must be same as we use in pulp_rpm.app.advisory.
    """
    pytest.skip(reason="Skip until issue #2268 addressed")

    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)

    # create remote with colliding advisory
    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(repository=repository, url=RPM_ADVISORY_INCOMPLETE_PKG_LIST_URL)

    error_msg = (
        "Incoming and existing advisories have the same id and timestamp "
        "but different and intersecting package lists, "
        "and neither package list is a proper subset of the other. "
        "At least one of the advisories is wrong. "
        "Advisory id: {}".format(RPM_ADVISORY_TEST_ID)
    )
    assert error_msg in exc.value.task.to_dict()["error"]["description"]


@pytest.mark.parallel
def test_sync_advisory_no_updated_date(init_and_sync):
    """Test sync advisory with no update.

    1. Sync repository with advisory which has updated_date
    2. Re-sync with repo with same id and version as previous
       but missing updated_date (issued_date should be used instead).
    """
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)
    repository_version = repository.latest_version_href

    repository, _ = init_and_sync(repository=repository, url=RPM_ADVISORY_NO_UPDATED_DATE)
    repository_version_new = repository.latest_version_href

    # TODO: this test isn't ideal because in this case the new advisory with no "updated_date"
    # has an "issued_date" older than the "updated_date" of the already-existing advisory,
    # therefore the new one gets ignored, and nothing happens. A better version of this test
    # would have a newer "issued_date" so that the advisory replaces the old one.
    assert repository_version_new == repository_version

    # added_advisory_date = [
    #     advisory["updated_date"]
    #     for advisory in get_added_content(repo.to_dict())[PULP_TYPE_ADVISORY]
    #     if RPM_ADVISORY_TEST_ID in advisory["id"]
    # ]
    # removed_advisory_date = [
    #     advisory["issued_date"]
    #     for advisory in get_removed_content(repo.to_dict())[PULP_TYPE_ADVISORY]
    #     if RPM_ADVISORY_TEST_ID in advisory["id"]
    # ]

    # self.assertGreater(
    #     parse_datetime(added_advisory_date[0]), parse_datetime(removed_advisory_date[0])
    # )


@pytest.mark.parallel
def test_sync_advisory_updated_update_date(init_and_sync):
    """Test sync advisory with updated update_date."""
    repository, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL)
    repository, _ = init_and_sync(repository=repository, url=RPM_UPDATED_UPDATEINFO_FIXTURE_URL)

    added_advisory_date = [
        advisory["updated_date"]
        for advisory in get_added_content(repository.to_dict())[PULP_TYPE_ADVISORY]
        if RPM_ADVISORY_TEST_ID_NEW in advisory["id"]
    ]
    removed_advisory_date = [
        advisory["updated_date"]
        for advisory in get_removed_content(repository.to_dict())[PULP_TYPE_ADVISORY]
        if RPM_ADVISORY_TEST_ID_NEW in advisory["id"]
    ]

    assert parse_datetime(added_advisory_date[0]) > parse_datetime(removed_advisory_date[0])


@pytest.mark.parallel
def test_sync_advisory_older_update_date(init_and_sync):
    """Test sync advisory with older update_date."""
    repository, _ = init_and_sync(url=RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
    advisory_date = [
        advisory["updated_date"]
        for advisory in get_content(repository.to_dict())[PULP_TYPE_ADVISORY]
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]

    repository, _ = init_and_sync(repository, url=RPM_UNSIGNED_FIXTURE_URL)
    advisory_date_new = [
        advisory["updated_date"]
        for advisory in get_content(repository.to_dict())[PULP_TYPE_ADVISORY]
        if advisory["id"] == RPM_ADVISORY_TEST_ID
    ]
    added_advisories = [
        advisory["id"] for advisory in get_added_content(repository.to_dict())[PULP_TYPE_ADVISORY]
    ]

    # check if advisory is preserved and no advisory with same id was added
    assert parse_datetime(advisory_date[0]) == parse_datetime(advisory_date_new[0])
    assert RPM_ADVISORY_TEST_ID not in added_advisories


@pytest.mark.parallel
def test_sync_repo_metadata_change(init_and_sync):
    """Sync RPM modular content."""
    repository, _ = init_and_sync(url=RPM_CUSTOM_REPO_METADATA_FIXTURE_URL)
    repository, _ = init_and_sync(
        repository=repository, url=RPM_CUSTOM_REPO_METADATA_CHANGED_FIXTURE_URL
    )

    # Check if repository was updated with repository metadata
    assert repository.latest_version_href.rstrip("/")[-1] == "2"
    assert PULP_TYPE_REPOMETADATA in get_added_content(repository.to_dict())


@pytest.mark.parallel
def test_sync_modular_static_context(init_and_sync):
    """Sync RPM modular content that includes the new static_context_field."""
    repository, _ = init_and_sync(url=RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL)

    summary = get_content_summary(repository.to_dict())
    added = get_added_content_summary(repository.to_dict())

    modules = get_content(repository.to_dict())[PULP_TYPE_MODULEMD]
    module_static_contexts = [
        (module["name"], module["version"]) for module in modules if module["static_context"]
    ]
    assert len(module_static_contexts) == 2
    assert summary == RPM_MODULAR_STATIC_FIXTURE_SUMMARY
    assert added == RPM_MODULAR_STATIC_FIXTURE_SUMMARY


@pytest.mark.parallel
@pytest.mark.parametrize("sync_policy", ["mirror_content_only", "additive"])
def test_sync_skip_srpm(init_and_sync, sync_policy):
    """In mirror_content_only mode, skip_types is allowed."""
    repository, _ = init_and_sync(
        url=SRPM_UNSIGNED_FIXTURE_URL, skip_types=["srpm"], sync_policy=sync_policy
    )

    present_package_count = len(get_content(repository.to_dict())[PULP_TYPE_PACKAGE])
    present_advisory_count = len(get_content(repository.to_dict())[PULP_TYPE_ADVISORY])
    assert present_package_count == 0
    assert present_advisory_count == SRPM_UNSIGNED_FIXTURE_ADVISORY_COUNT


@pytest.mark.parallel
def test_sha_checksum(init_and_sync):
    """Test that we can sync a repo using SHA as a checksum."""
    init_and_sync(url=RPM_SHA_FIXTURE_URL)


@pytest.mark.parallel
def test_one_nevra_two_locations_and_checksums(init_and_sync):
    """Sync a repository known to have one nevra, in two locations, with different content.

    While 'odd', this is a real-world occurrence.
    """
    init_and_sync(url=CENTOS7_OPSTOOLS_URL, policy="on_demand")


@pytest.mark.parallel
def test_requires_urlencoded_paths(init_and_sync):
    """Sync a repository known to FAIL when an RPM has non-urlencoded characters in its path.

    See Amazon, java-11-amazon-corretto-javadoc-11.0.8+10-1.amzn2.x86_64.rpm.

    NOTE: testing that this 'works' requires testing against a webserver that does
    whatever-it-is that Amazon's backend is doing. That's why it requires the external repo.
    The rest of the pulp_rpm test-suite is showing us that the code for this fix isn't
    breaking anyone *else*...
    """
    init_and_sync(url=AMAZON_MIRROR, policy="on_demand")


@pytest.mark.parallel
def test_invalid_url(init_and_sync):
    """Sync a repository using a remote url that does not exist."""
    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(url="http://i-am-an-invalid-url.com/invalid/")

    assert exc.value.task.to_dict()["error"]["description"] is not None


@pytest.mark.parallel
def test_invalid_rpm_content(init_and_sync):
    """Sync a repository using an invalid plugin_content repository."""
    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(url=RPM_INVALID_FIXTURE_URL)

    for key in ("missing", "filelists.xml"):
        assert key in exc.value.task.to_dict()["error"]["description"]


@pytest.mark.parallel
def test_sync_metadata_with_unsupported_checksum_type(init_and_sync):
    """
    Sync an RPM repository with an unsupported checksum (md5).

    This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
    """
    if "md5" in settings.ALLOWED_CONTENT_CHECKSUMS:
        pytest.skip(
            reason="Cannot verify the expected hasher error if the 'MD5' checksum is allowed."
        )

    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(url=RPM_MD5_REPO_FIXTURE_URL)

    assert (
        "does not contain at least one trusted hasher which "
        "is specified in the 'ALLOWED_CONTENT_CHECKSUMS'"
    ) in exc.value.task.to_dict()["error"]["description"]


@pytest.mark.parallel
def test_sync_packages_with_unsupported_checksum_type(init_and_sync):
    """
    Sync an RPM repository with an unsupported checksum (md5) used for packages.

    This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
    """
    pytest.skip(
        reason=(
            "Needs a repo where an unacceptable checksum is used for packages, but not for metadata"
        )
    )

    if "md5" in settings.ALLOWED_CONTENT_CHECKSUMS:
        pytest.skip(
            reason="Cannot verify the expected hasher error if the 'MD5' checksum is allowed."
        )

    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(url="https://fixtures.com/packages_with_unsupported_checksum")

    error_description = exc.value.task.to_dict()["error"]["description"]
    assert "rpm-with-md5/bear-4.1.noarch.rpm contains forbidden checksum type" in error_description


@pytest.mark.parallel
def test_complete_mirror_with_xml_base_fails(init_and_sync):
    """Test that syncing a repository that uses xml:base in mirror mode fails."""
    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(url=REPO_WITH_XML_BASE_URL, sync_policy="mirror_complete")

    error_description = exc.value.task.to_dict()["error"]["description"]
    assert "features which are incompatible with 'mirror' sync" in error_description


@pytest.mark.parallel
def test_complete_mirror_with_external_location_href_fails(init_and_sync):
    """
    Test that syncing a repository that contains an external location_href fails in mirror mode.

    External location_href refers to a location_href that points outside of the repo,
    e.g. ../../Packages/blah.rpm
    """
    pytest.skip(reason="Needs a repository that links content to a remote source")

    with pytest.raises(PulpTaskError) as exc:
        init_and_sync(
            url="https://fixtures.com/repo_with_external_data", sync_policy="mirror_complete"
        )

    error_description = exc.value.task.to_dict()["error"]["description"]
    assert "features which are incompatible with 'mirror' sync" in error_description


# We can restore this test when we are able to generate repositories on-demand. We just need to
# create a "prestodelta" entry in the repomd.xml, we need not have it actually be a valid one.
@pytest.mark.skip("No DRPM fixture repo.")
@pytest.mark.parallel
def test_complete_mirror_with_delta_metadata_fails(init_and_sync):
    """
    Test that syncing a repository that contains prestodelta metadata fails in mirror mode.

    Otherwise we would be mirroring the metadata without mirroring the DRPM packages.
    """
    with pytest.raises(PulpTaskError) as exc:
        pass
        # init_and_sync(url=DRPM_UNSIGNED_FIXTURE_URL, sync_policy="mirror_complete")

    error_description = exc.value.task.to_dict()["error"]["description"]
    assert "features which are incompatible with 'mirror' sync" in error_description


@pytest.mark.parallel
def test_mirror_and_sync_policy_provided_simultaneously_fails(
    gen_object_with_cleanup,
    rpm_repository_api,
    rpm_rpmremote_api,
):
    """
    Test that syncing fails if both the "mirror" and "sync_policy" params are provided.
    """
    repository = gen_object_with_cleanup(rpm_repository_api, gen_repo())
    remote = gen_object_with_cleanup(
        rpm_rpmremote_api, gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
    )

    repository_sync_data = RpmRepositorySyncURL(
        remote=remote.pulp_href, sync_policy="mirror_complete", mirror=True
    )

    with pytest.raises(ApiException):
        rpm_repository_api.sync(repository.pulp_href, repository_sync_data)


@pytest.mark.parallel
def test_sync_skip_srpm_fails_mirror_complete(init_and_sync):
    """Test that sync is rejected if both skip_types and mirror_complete are configured."""
    with pytest.raises(ApiException):
        init_and_sync(
            url=SRPM_UNSIGNED_FIXTURE_URL, skip_types=["srpm"], sync_policy="mirror_complete"
        )


@pytest.mark.parallel
def test_core_metadata(init_and_sync, rpm_package_api):
    """Test that the metadata returned by the Pulp API post-sync matches what we expect.

    Do the following:

    1. Sync a repo.
    2. Query package metadata from the API.
    3. Match it against the metadata that we expect to be there.
    """
    repository, _ = init_and_sync(url=RPM_COMPLEX_FIXTURE_URL, policy="on_demand")

    package = rpm_package_api.list(
        name=RPM_COMPLEX_PACKAGE_DATA["name"], repository_version=repository.latest_version_href
    ).results[0]
    package = package.to_dict()

    # sort file and changelog metadata
    package["changelogs"].sort(reverse=True)
    for metadata in [package, RPM_COMPLEX_PACKAGE_DATA]:
        # the list-of-lists can't be sorted easily so we produce a string representation
        files = []
        for f in metadata["files"]:
            files.append(
                "{basename}{filename} type={type}".format(
                    basename=f[1], filename=f[2], type=f[0] or "file"
                )
            )
        metadata["files"] = sorted(files)

    # TODO: figure out how to un-ignore "time_file" without breaking the tests
    diff = dictdiffer.diff(
        package, RPM_COMPLEX_PACKAGE_DATA, ignore={"time_file", "pulp_created", "pulp_href"}
    )
    assert list(diff) == [], list(diff)

    # assert no package is marked modular
    for pkg in get_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
        assert pkg["is_modular"] is False


@pytest.mark.parallel
def test_treeinfo_metadata(init_and_sync, rpm_content_distribution_trees_api):
    """Test that the metadata returned by the Pulp API post-sync matches what we expect.

    Do the following:

    1. Sync a repo.
    2. Query treeinfo metadata from the API.
    3. Match it against the metadata that we expect to be there.
    """
    repository, _ = init_and_sync(url=RPM_KICKSTART_FIXTURE_URL, policy="on_demand")

    distribution_tree = rpm_content_distribution_trees_api.list(
        repository_version=repository.latest_version_href
    ).results[0]
    distribution_tree = distribution_tree.to_dict()
    # delete pulp-specific metadata
    distribution_tree.pop("pulp_href")

    # sort kickstart metadata so that we can compare the dicts properly
    for d in [distribution_tree, RPM_KICKSTART_DATA]:
        d["addons"] = sorted(d["addons"], key=lambda x: x["addon_id"])
        d["images"] = sorted(d["images"], key=lambda x: x["path"])
        d["checksums"] = sorted(d["checksums"], key=lambda x: x["path"])
        d["variants"] = sorted(d["variants"], key=lambda x: x["variant_id"])

    for image in distribution_tree["images"]:
        image.pop("artifact")

    diff = dictdiffer.diff(distribution_tree, RPM_KICKSTART_DATA)
    assert list(diff) == [], list(diff)


def test_modular_metadata(
    init_and_sync,
    rpm_modulemd_api,
    rpm_modulemd_defaults_api,
    rpm_modulemd_obsoletes_api,
    delete_orphans_pre,
):
    """Test that the metadata returned by the Pulp API post-sync matches what we expect.

    Do the following:

    1. Sync a repo.
    2. Query modular metadata from the API.
    3. Match it against the metadata that we expect to be there.
    """
    repository, _ = init_and_sync(url=RPM_MODULAR_FIXTURE_URL, policy="on_demand")

    modules = [
        md.to_dict()
        for md in rpm_modulemd_api.list(repository_version=repository.latest_version_href).results
    ]
    module_defaults = [
        md.to_dict()
        for md in rpm_modulemd_defaults_api.list(
            repository_version=repository.latest_version_href
        ).results
    ]
    module_obsoletes = [
        md.to_dict()
        for md in rpm_modulemd_obsoletes_api.list(
            repository_version=repository.latest_version_href
        ).results
    ]

    def module_key(m):
        return f"{m['name']}-{m['stream']}-{m['version']}-{m['context']}-{m['arch']}"

    def module_default_key(m):
        return f"{m['module']}-{m['stream']}"

    def module_obsolete_key(m):
        return f"{m['module_name']}-{m['module_stream']}"

    modules.sort(key=module_key)
    module_defaults.sort(key=module_default_key)
    module_obsoletes.sort(key=module_obsolete_key)

    RPM_MODULEMDS_DATA.sort(key=module_key)
    RPM_MODULEMD_DEFAULTS_DATA.sort(key=module_default_key)
    RPM_MODULEMD_OBSOLETES_DATA.sort(key=module_obsolete_key)

    for m1, m2 in zip(modules, RPM_MODULEMDS_DATA):
        diff = dictdiffer.diff(m1, m2, ignore={"packages", "pulp_created", "pulp_href"})
        assert list(diff) == [], list(diff)

    for m1, m2 in zip(module_defaults, RPM_MODULEMD_DEFAULTS_DATA):
        diff = dictdiffer.diff(m1, m2, ignore={"pulp_created", "pulp_href"})
        assert list(diff) == [], list(diff)

    for m1, m2 in zip(module_obsoletes, RPM_MODULEMD_OBSOLETES_DATA):
        diff = dictdiffer.diff(m1, m2, ignore={"pulp_created", "pulp_href"})
        assert list(diff) == [], list(diff)

    # assert all package from modular repo is marked as modular
    for pkg in get_content(repository.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
        assert pkg["is_modular"] is True


@pytest.mark.parallel
def test_additive_mode(init_and_sync):
    """Test of additive mode.

    1. Create repository, remote and sync it
    2. Create remote with different set of content
    3. Re-sync and check if new content was added and is present with old one
    """
    repository, remote = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
    repository, _ = init_and_sync(
        repository=repository,
        url=SRPM_UNSIGNED_FIXTURE_URL,
        policy="on_demand",
        sync_policy="additive",
    )

    present_package_count = len(get_content(repository.to_dict())[PULP_TYPE_PACKAGE])
    present_advisory_count = len(get_content(repository.to_dict())[PULP_TYPE_ADVISORY])

    assert (RPM_PACKAGE_COUNT + SRPM_UNSIGNED_FIXTURE_PACKAGE_COUNT) == present_package_count
    assert (RPM_ADVISORY_COUNT + SRPM_UNSIGNED_FIXTURE_ADVISORY_COUNT) == present_advisory_count


@pytest.mark.parallel
@pytest.mark.parametrize("sync_policy", ["mirror_complete", "mirror_content_only"])
def test_mirror_mode(sync_policy, init_and_sync, rpm_publication_api):
    """Test of mirror mode."""
    repository, remote = init_and_sync(url=SRPM_UNSIGNED_FIXTURE_URL, policy="on_demand")

    assert repository.latest_version_href == f"{repository.pulp_href}versions/1/"
    assert rpm_publication_api.list(repository_version=repository.latest_version_href).count == 0

    repository, _ = init_and_sync(
        repository=repository, url=RPM_SIGNED_FIXTURE_URL, sync_policy=sync_policy
    )

    # check that one publication was created w/ no repository versions
    # and only the new content is present
    assert get_content_summary(repository.to_dict()) == RPM_FIXTURE_SUMMARY
    assert repository.latest_version_href == f"{repository.pulp_href}versions/2/"

    if sync_policy == "mirror_complete":
        created_publications = rpm_publication_api.list(
            repository_version=repository.latest_version_href
        ).count
        assert created_publications == 1
