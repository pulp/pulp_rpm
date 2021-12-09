"""Tests that sync rpm plugin repositories."""
import os
import unittest
from random import choice

import dictdiffer
from django.utils.dateparse import parse_datetime

from pulp_smash import cli, config
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTaskError,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_added_content,
    get_content,
    get_content_summary,
    get_removed_content,
    modify_repo,
    wget_download_on_host,
)
from pulp_smash.utils import get_pulp_setting

from pulp_rpm.tests.functional.constants import (
    AMAZON_MIRROR,
    DRPM_UNSIGNED_FIXTURE_URL,
    CENTOS7_OPSTOOLS,
    PULP_TYPE_ADVISORY,
    PULP_TYPE_MODULEMD,
    PULP_TYPE_PACKAGE,
    PULP_TYPE_REPOMETADATA,
    REPO_WITH_XML_BASE_URL,
    REPO_WITH_EXTERNAL_LOCATION_HREF_URL,
    RPM_ADVISORY_CONTENT_NAME,
    RPM_ADVISORY_COUNT,
    RPM_ADVISORY_DIFFERENT_PKGLIST_URL,
    RPM_ADVISORY_DIFFERENT_REPO_URL,
    RPM_ADVISORY_INCOMPLETE_PKG_LIST_URL,
    RPM_ADVISORY_NO_DATES,
    RPM_ADVISORY_TEST_ADDED_COUNT,
    RPM_ADVISORY_TEST_ID,
    RPM_ADVISORY_TEST_ID_NEW,
    RPM_ADVISORY_TEST_REMOVE_COUNT,
    RPM_ADVISORY_UPDATED_VERSION_URL,
    RPM_CUSTOM_REPO_METADATA_CHANGED_FIXTURE_URL,
    RPM_CUSTOM_REPO_METADATA_FIXTURE_URL,
    RPM_EPEL_URL,
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
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
    progress_reports,
    skip_if,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    ContentDistributionTreesApi,
    ContentPackagesApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
    PublicationsRpmApi,
)


class BasicSyncTestCase(PulpTestCase):
    """Sync a repository with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.packages_api = ContentPackagesApi(cls.client)

        delete_orphans()

    def test_sync(self):
        """Sync repositories with the rpm plugin.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as version '0'. After a sync the repository version is updated.

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Assert that the correct number of units were added and are present
           in the repo.
        6. Sync the remote one more time.
        7. Assert that repository version is different from the previous one.
        8. Assert that the same number of are present and that no units were
           added.
        """
        repo, remote = self.do_test()

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

        # Sync the repository again.
        latest_version_href = repo.latest_version_href
        repo, remote = self.do_test(repo, remote)

        self.assertEqual(latest_version_href, repo.latest_version_href)
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

    def test_sync_local(self):
        """Test syncing from the local filesystem."""
        wget_download_on_host(RPM_UNSIGNED_FIXTURE_URL, "/tmp")
        remote = self.remote_api.create(gen_rpm_remote(url="file:///tmp/rpm-unsigned/"))

        repo, remote = self.do_test(remote=remote, mirror=True)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

    def test_sync_from_valid_mirror_list_feed(self):
        """Sync RPM content from a mirror list feed which contains a valid remote URL."""
        remote = self.remote_api.create(gen_rpm_remote(RPM_MIRROR_LIST_GOOD_FIXTURE_URL))
        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

    def test_sync_from_valid_mirror_list_feed_with_params(self):
        """Sync RPM content from a mirror list feed which contains a valid remote URL."""
        remote = self.remote_api.create(gen_rpm_remote(RPM_EPEL_MIRROR_URL))
        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

    def test_sync_from_invalid_mirror_list_feed(self):
        """Sync RPM content from a mirror list feed which contains an invalid remote URL."""
        repo = self.repo_api.create(gen_repo())
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")

        remote = self.remote_api.create(gen_rpm_remote(RPM_MIRROR_LIST_BAD_FIXTURE_URL))
        remote = self.remote_api.read(remote.pulp_href)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        try:
            monitor_task(sync_response.task)
        except PulpTaskError as exc:
            self.assertIn(
                "An invalid remote URL was provided", exc.task.to_dict()["error"]["description"]
            )
        else:
            self.fail("A task was completed without a failure.")

    def test_sync_modular(self):
        """Sync RPM modular content.

        This test targets the following issue:

        * `Pulp #5408 <https://pulp.plan.io/issues/5408>`_
        """
        body = gen_rpm_remote(RPM_MODULAR_FIXTURE_URL)
        remote = self.remote_api.create(body)

        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_MODULAR_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_MODULAR_FIXTURE_SUMMARY)

    def test_checksum_constraint(self):
        """Verify checksum constraint test case.

        Do the following:

        1. Create and sync a repo using the following
           url=RPM_REFERENCES_UPDATEINFO_URL.
        2. Create and sync a secondary repo using the following
           url=RPM_UNSIGNED_FIXTURE_URL.
           Those urls have RPM packages with the same name.
        3. Assert that the task succeed.

        This test targets the following issue:

        * `Pulp #4170 <https://pulp.plan.io/issues/4170>`_
        * `Pulp #4255 <https://pulp.plan.io/issues/4255>`_
        """
        for repository in [RPM_REFERENCES_UPDATEINFO_URL, RPM_UNSIGNED_FIXTURE_URL]:
            body = gen_rpm_remote(repository)
            remote = self.remote_api.create(body)

            repo, remote = self.do_test(remote=remote)

            self.addCleanup(self.repo_api.delete, repo.pulp_href)
            self.addCleanup(self.remote_api.delete, remote.pulp_href)

            self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
            self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

    def test_sync_epel_repo(self):
        """Sync large EPEL repository."""
        if "JENKINS_HOME" not in os.environ:
            raise unittest.SkipTest("Slow test. It should only run on Jenkins")

        body = gen_rpm_remote(RPM_EPEL_URL)
        remote = self.remote_api.create(body)

        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        content_summary = get_content_summary(repo.to_dict())
        self.assertGreater(content_summary[RPM_PACKAGE_CONTENT_NAME], 0)

    def test_kickstart_immediate(self):
        """Test syncing kickstart repositories."""
        self.do_kickstart_test("immediate")

    def test_kickstart_on_demand(self):
        """Test syncing kickstart repositories."""
        self.do_kickstart_test("on_demand")

    def do_kickstart_test(self, policy):
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
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL, policy=policy)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_KICKSTART_FIXTURE_SUMMARY)
        self.assertDictEqual(
            get_added_content_summary(repo.to_dict()), RPM_KICKSTART_FIXTURE_SUMMARY
        )

        latest_version_href = repo.latest_version_href

        # sync again
        repo, remote = self.do_test(repository=repo, remote=remote)

        # Test distribution tree API
        dist_tree_api = ContentDistributionTreesApi(self.client)
        self.assertEqual(dist_tree_api.list().results[0].release_short, "RHEL")

        # Check that nothing has changed since the last sync.
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_KICKSTART_FIXTURE_SUMMARY)
        self.assertEqual(latest_version_href, repo.latest_version_href)

    def test_mutated_packages(self):
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
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # check if sync OK
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

        # Save a copy of the original packages.
        original_packages = {
            (
                content["name"],
                content["epoch"],
                content["version"],
                content["release"],
                content["arch"],
            ): content
            for content in get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]
        }

        # Create a remote with a different test fixture with the same NEVRA but
        # different digests.
        body = gen_rpm_remote(RPM_SIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync again
        repo, remote = self.do_test(repo, remote)

        # In case of "duplicates" the most recent one is chosen, so the old
        # package is removed from and the new one is added to a repo version.
        self.assertEqual(
            len(get_added_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]),
            RPM_PACKAGE_COUNT,
            get_added_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME],
        )
        self.assertEqual(
            len(get_removed_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]),
            RPM_PACKAGE_COUNT,
            get_removed_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME],
        )

        # Test that the packages have been modified.
        mutated_packages = {
            (
                content["name"],
                content["epoch"],
                content["version"],
                content["release"],
                content["arch"],
            ): content
            for content in get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]
        }

        for nevra in original_packages:
            with self.subTest(pkg=nevra):
                self.assertNotEqual(
                    original_packages[nevra]["pkgId"],
                    mutated_packages[nevra]["pkgId"],
                    original_packages[nevra]["pkgId"],
                )

    def test_sync_diff_checksum_packages(self):
        """Sync two fixture content with same NEVRA and different checksum.

        Make sure we end up with the most recently synced content.

        Do the following:

        1. Create two remotes with same content but different checksums.
            Sync the remotes one after the other.
               a. Sync remote with packages with SHA256: ``RPM_UNSIGNED_FIXTURE_URL``.
               b. Sync remote with packages with SHA512: ``RPM_SHA512_FIXTURE_URL``.
        2. Make sure the latest content is only kept.

        This test targets the following issues:

        * `Pulp #4297 <https://pulp.plan.io/issues/4297>`_
        * `Pulp #3954 <https://pulp.plan.io/issues/3954>`_
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
        remote = self.remote_api.create(body)

        # sync with SHA256
        repo, remote = self.do_test(remote=remote)

        body = gen_rpm_remote(RPM_SHA512_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # re-sync with SHA512
        repo, remote = self.do_test(repo, remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        added_content = get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]
        removed_content = get_removed_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]

        # In case of "duplicates" the most recent one is chosen, so the old
        # package is removed from and the new one is added to a repo version.
        self.assertEqual(len(added_content), RPM_PACKAGE_COUNT)
        self.assertEqual(len(removed_content), RPM_PACKAGE_COUNT)

        # Verifying whether the packages with first checksum is removed and second
        # is added.
        self.assertEqual(added_content[0]["checksum_type"], "sha512")
        self.assertEqual(removed_content[0]["checksum_type"], "sha256")

    def test_mutated_advisory_metadata(self):
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
        # Create a remote with the unsigned RPM fixture url.
        # We need to use the unsigned fixture because the one used down below
        # has unsigned RPMs. Signed and unsigned units have different hashes,
        # so they're seen as different units.
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # check if sync OK
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

        original_updaterecords = {
            content["id"]: content
            for content in get_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]
        }

        body = gen_rpm_remote(RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync the repository again
        repo, remote = self.do_test(repo, remote)

        # add the second remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertEqual(len(get_added_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]), 4)
        self.assertEqual(len(get_removed_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]), 4)

        # Test that the updateinfo have been modified.
        mutated_updaterecords = {
            content["id"]: content
            for content in get_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]
        }

        self.assertNotEqual(mutated_updaterecords, original_updaterecords)
        self.assertEqual(
            mutated_updaterecords[RPM_ADVISORY_TEST_ID_NEW]["description"],
            "Updated Gorilla_Erratum and the updated date contains timezone",
            mutated_updaterecords[RPM_ADVISORY_TEST_ID_NEW],
        )

    def test_optimize(self):
        """Sync is no-op without changes.

        This test targets the following issue:

        `Pulp #6313 <https://pulp.plan.io/issues/6313>`_

        If there are no changes, a full sync should not be done.

        Do the following:

        1. Sync (a repo and a remote will be created automatically).
        2. Sync again to get our task dictionary.
        3. Assert an "Optimizing Sync" progress report is present.
        4. Sync again with flag "optimize=False".
        5. Assert "Optimizing Sync" progress report is absent.
        # 6. **Create a new repo version.
        # 7. Sync again (no flag).
        # 8. Assert "Optimizing Sync" progress report is absent.
        9. Update remote to have "policy=immediate".
        10. Sync again.
        11. Assert "Optimizing Sync" progress report is absent.
        12. Create a new (different) remote.
        13. Sync using the new remote.
        14. Assert "Optimizing Sync" progress report is absent.
        # 15. Sync again with the new remote.
        # 16. Assert an "Optimizing Sync" progress report is present.
        """
        # sync
        repo, remote = self.do_test()

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # sync, get progress reports from task
        report_list = self.sync(repository=repo, remote=remote)

        # check for an optimization progress report
        optimized = self.optimize_report(progress_reports=report_list)

        # check that sync was optimized
        self.assertTrue(optimized)

        # sync again with flag optimize=False
        report_list = self.sync(repository=repo, remote=remote, optimize=False)

        # check for an optimization progress report
        optimized = self.optimize_report(progress_reports=report_list)

        # check that sync was not optimized
        self.assertFalse(optimized)

        # create a new repo version
        content = choice(get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME])
        modify_repo(config.get_config(), repo.to_dict(), remove_units=[content])

        # sync, get progress reports from task
        report_list = self.sync(repository=repo, remote=remote)

        # check for an optimization progress report
        optimized = self.optimize_report(progress_reports=report_list)

        # check that sync was not optimized
        self.assertFalse(optimized)

        # update remote
        body = {"policy": "immediate"}
        response = self.remote_api.partial_update(remote.pulp_href, body)
        monitor_task(response.task)

        # sync, get progress reports from task
        report_list = self.sync(repository=repo, remote=remote)

        # check for an optimization progress report
        optimized = self.optimize_report(progress_reports=report_list)

        # check that sync was not optimized
        self.assertFalse(optimized)

        # create new remote
        body = gen_rpm_remote()
        body["url"] = RPM_RICH_WEAK_FIXTURE_URL
        new_remote = self.remote_api.create(body)

        # add resource to clean up
        self.addCleanup(self.remote_api.delete, new_remote.pulp_href)

        # sync with new remote
        report_list = self.sync(repository=repo, remote=new_remote)

        # check for an optimization progress report
        optimized = self.optimize_report(progress_reports=report_list)

        # check that sync was not optimized
        self.assertFalse(optimized)

        # sync again with new remote
        report_list = self.sync(repository=repo, remote=new_remote)

        # check for an optimization progress report
        optimized = self.optimize_report(progress_reports=report_list)

        # check that sync was optimized
        self.assertTrue(optimized)

    def test_mirror_mode_optimize(self):
        """
        Ensure mirror mode and optimize work correctly together.

        Content is fully present and sync is optimized.

        Do the following:
        1. Sync (a repo and a remote will be created automatically).
        2. Sync again with optimize=True and mirror=True
        3. Assert an "Optimizing Sync" progress report is present.
        4. Assert that no changes were made to a repo.
        """
        # sync
        repo, remote = self.do_test()
        first_sync_repo_version = repo.latest_version_href

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # re-sync, get progress reports from task
        report_list = self.sync(repository=repo, remote=remote, optimize=True, mirror=True)
        second_sync_repo_version = repo.latest_version_href

        is_optimized = self.optimize_report(progress_reports=report_list)
        self.assertTrue(is_optimized)

        self.assertEqual(first_sync_repo_version, second_sync_repo_version)

    def test_sync_advisory_new_version(self):
        """Sync a repository and re-sync with newer version of Advisory.

        Test if advisory with same ID and pkglist, but newer version is updated.

        `Pulp #4142 <https://pulp.plan.io/issues/4142>`_

        1. Sync rpm-unsigned repository
        2. Re-sync rpm-advisory-updateversion
        3. Check if the newer version advisory was synced
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_ADVISORY_UPDATED_VERSION_URL)
        remote = self.remote_api.create(body)

        # re-sync
        repo, remote = self.do_test(repo, remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # check if newer version advisory was added and older removed
        added_advisories = get_added_content(repo.to_dict())[PULP_TYPE_ADVISORY]
        added_advisory = [
            advisory["version"]
            for advisory in added_advisories
            if advisory["id"] == RPM_ADVISORY_TEST_ID
        ]
        removed_advisories = get_removed_content(repo.to_dict())[PULP_TYPE_ADVISORY]
        removed_advisory = [
            advisory["version"]
            for advisory in removed_advisories
            if advisory["id"] == RPM_ADVISORY_TEST_ID
        ]
        self.assertGreater(int(added_advisory[0]), int(removed_advisory[0]))

    def test_sync_advisory_old_version(self):
        """Sync a repository and re-sync with older version of Advisory.

        Test if advisory with same ID and pkglist, but older version is not updated.

        `Pulp #4142 <https://pulp.plan.io/issues/4142>`_

        1. Sync rpm-advisory-updateversion
        2. Re-sync rpm-unsigned repository
        3. Check if the newer (already present) version is preserved
        """
        body = gen_rpm_remote(RPM_ADVISORY_UPDATED_VERSION_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)
        repository_version = repo.to_dict()["latest_version_href"]

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # re-sync
        repo, remote = self.do_test(repo, remote)
        repository_version_new = repo.to_dict()["latest_version_href"]

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        present_advisories = get_content(repo.to_dict())[PULP_TYPE_ADVISORY]
        advisory_version = [
            advisory["version"]
            for advisory in present_advisories
            if advisory["id"] == RPM_ADVISORY_TEST_ID
        ]

        # check if the newer version is preserved
        self.assertEqual(advisory_version[0], "2")
        # no new content is present in RPM_UNSIGNED_FIXTURE_URL against
        # RPM_ADVISORY_UPDATED_VERSION_URL so repository latests version should stay the same.
        self.assertEqual(repository_version, repository_version_new)

    def test_sync_merge_advisories(self):
        """Sync two advisories with same ID, version and different pkglist.

        Test if two advisories are merged.
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_ADVISORY_DIFFERENT_PKGLIST_URL)
        remote = self.remote_api.create(body)

        # re-sync
        repo, remote = self.do_test(repo, remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # check advisories were merged
        added_advisories = get_added_content(repo.to_dict())[PULP_TYPE_ADVISORY]
        added_advisory_pkglist = [
            advisory["pkglist"]
            for advisory in added_advisories
            if advisory["id"] == RPM_ADVISORY_TEST_ID
        ]
        removed_advisories = get_removed_content(repo.to_dict())[PULP_TYPE_ADVISORY]
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
        self.assertEqual(RPM_ADVISORY_TEST_REMOVE_COUNT, removed_count)
        self.assertEqual(RPM_ADVISORY_TEST_ADDED_COUNT, added_count)

    def test_sync_advisory_diff_repo(self):
        """Test failure sync advisories.

        If advisory has same id, version but different update_date and
        no packages intersection sync should fail.

        Tested error_msg must be same as we use in pulp_rpm.app.advisory.

        NOTE: If ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION is True, this test
        will fail since the errata-merge will be allowed.
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # create remote with colliding advisory
        body = gen_rpm_remote(RPM_ADVISORY_DIFFERENT_REPO_URL)
        remote = self.remote_api.create(body)
        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        with self.assertRaises(PulpTaskError) as exc:
            monitor_task(sync_response.task)

        task_result = exc.exception.task.to_dict()
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
        self.assertIn(error_msg, task_result["error"]["description"])

    def test_sync_advisory_proper_subset_pgk_list(self):
        """Test success: sync advisories where pkglist is proper-subset of another.

        If update_dates and update_version are the same, pkglist intersection is non-empty
        and a proper-subset of the 'other' pkglist, sync should succeed.
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # create remote with colliding advisory
        body = gen_rpm_remote(RPM_ADVISORY_INCOMPLETE_PKG_LIST_URL)
        remote = self.remote_api.create(body)
        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        try:
            monitor_task(sync_response.task)
        except Exception as e:
            self.fail("Unexpected exception {}".format(e.message))

    @unittest.skip("skip until issue #8335 addressed")
    def test_sync_advisory_incomplete_pgk_list(self):
        """Test failure sync advisories.

        If update_dates and update_version are the same, pkglist intersection is non-empty
        and not equal to either pkglist sync should fail.

        Tested error_msg must be same as we use in pulp_rpm.app.advisory.
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # create remote with colliding advisory
        body = gen_rpm_remote(RPM_ADVISORY_INCOMPLETE_PKG_LIST_URL)
        remote = self.remote_api.create(body)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        with self.assertRaises(PulpTaskError) as cm:
            monitor_task(sync_response.task)
        task_result = cm.exception.task.to_dict()
        error_msg = (
            "Incoming and existing advisories have the same id and timestamp "
            "but different and intersecting package lists, "
            "and neither package list is a proper subset of the other. "
            "At least one of the advisories is wrong. "
            "Advisory id: {}".format(RPM_ADVISORY_TEST_ID)
        )

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.assertIn(error_msg, task_result["error"]["description"])

    @unittest.skip("FIXME: Enable this test after https://pulp.plan.io/issues/6605 is fixed")
    def test_sync_advisory_no_updated_date(self):
        """Test sync advisory with no update.

        1. Sync repository with advisory which has updated_date
        2. Re-sync with repo with same id and version as previous
           but missing updated_date (issued_date should be used instead).
        """
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_ADVISORY_NO_DATES)
        remote = self.remote_api.create(body)

        # re-sync
        repo, remote = self.do_test(repo, remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        added_advisory_date = [
            advisory["updated_date"]
            for advisory in get_added_content(repo.to_dict())[PULP_TYPE_ADVISORY]
            if RPM_ADVISORY_TEST_ID in advisory["id"]
        ]
        removed_advisory_date = [
            advisory["issued_date"]
            for advisory in get_removed_content(repo.to_dict())[PULP_TYPE_ADVISORY]
            if RPM_ADVISORY_TEST_ID in advisory["id"]
        ]

        self.assertGreater(
            parse_datetime(added_advisory_date[0]), parse_datetime(removed_advisory_date[0])
        )

    def test_sync_advisory_updated_update_date(self):
        """Test sync advisory with updated update_date."""
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # re-sync
        repo, remote = self.do_test(repo, remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        added_advisory_date = [
            advisory["updated_date"]
            for advisory in get_added_content(repo.to_dict())[PULP_TYPE_ADVISORY]
            if RPM_ADVISORY_TEST_ID_NEW in advisory["id"]
        ]
        removed_advisory_date = [
            advisory["updated_date"]
            for advisory in get_removed_content(repo.to_dict())[PULP_TYPE_ADVISORY]
            if RPM_ADVISORY_TEST_ID_NEW in advisory["id"]
        ]

        self.assertGreater(
            parse_datetime(added_advisory_date[0]), parse_datetime(removed_advisory_date[0])
        )

    def test_sync_advisory_older_update_date(self):
        """Test sync advisory with older update_date."""
        body = gen_rpm_remote(RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_test(remote=remote)
        advisory_date = [
            advisory["updated_date"]
            for advisory in get_content(repo.to_dict())[PULP_TYPE_ADVISORY]
            if advisory["id"] == RPM_ADVISORY_TEST_ID
        ]

        # add remote to clean up
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # re-sync
        repo, remote = self.do_test(repo, remote)

        advisory_date_new = [
            advisory["updated_date"]
            for advisory in get_content(repo.to_dict())[PULP_TYPE_ADVISORY]
            if advisory["id"] == RPM_ADVISORY_TEST_ID
        ]
        added_advisories = [
            advisory["id"] for advisory in get_added_content(repo.to_dict())[PULP_TYPE_ADVISORY]
        ]

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # check if advisory is preserved and no advisory with same id was added
        self.assertEqual(parse_datetime(advisory_date[0]), parse_datetime(advisory_date_new[0]))
        self.assertNotIn(RPM_ADVISORY_TEST_ID, added_advisories)

    def test_sync_repo_metadata_change(self):
        """Sync RPM modular content.

        This test targets sync issue when only custom metadata changes:

        * `Pulp #7030 <https://pulp.plan.io/issues/7030>`_
        """
        body = gen_rpm_remote(RPM_CUSTOM_REPO_METADATA_FIXTURE_URL)
        remote = self.remote_api.create(body)

        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        body = gen_rpm_remote(RPM_CUSTOM_REPO_METADATA_CHANGED_FIXTURE_URL)
        remote_changed = self.remote_api.create(body)

        self.addCleanup(self.remote_api.delete, remote_changed.pulp_href)

        repo, remote = self.do_test(repository=repo, remote=remote_changed)

        # Check if repository was updated with repository metadata
        self.assertEqual(repo.latest_version_href.rstrip("/")[-1], "2")
        self.assertTrue(PULP_TYPE_REPOMETADATA in get_added_content(repo.to_dict()))

    @unittest.skip("Skip until we can get libmodulemd-2.12 on CentOS-8")
    def test_sync_modular_static_context(self):
        """Sync RPM modular content that includes the new static_context_field.

        See `#8638 <https://pulp.plan.io/issues/8638>`_ for details.
        """
        body = gen_rpm_remote(RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL)
        remote = self.remote_api.create(body)

        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        summary = get_content_summary(repo.to_dict())
        added = get_added_content_summary(repo.to_dict())

        modules = get_content(repo.to_dict())[PULP_TYPE_MODULEMD]
        module_static_contexts = [
            (module["name"], module["version"]) for module in modules if module["static_context"]
        ]
        self.assertTrue(len(module_static_contexts) == 2)
        self.assertDictEqual(summary, RPM_MODULAR_STATIC_FIXTURE_SUMMARY)
        self.assertDictEqual(added, RPM_MODULAR_STATIC_FIXTURE_SUMMARY)

    def test_sync_skip_srpm(self):
        """Sync everything but not SRPMs."""
        body = gen_rpm_remote(SRPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)
        repo = self.repo_api.create(gen_repo())
        self.sync(repository=repo, remote=remote, skip_types=["srpm"])

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repo = self.repo_api.read(repo.pulp_href)
        present_package_count = len(get_content(repo.to_dict())[PULP_TYPE_PACKAGE])
        present_advisory_count = len(get_content(repo.to_dict())[PULP_TYPE_ADVISORY])
        self.assertEqual(present_package_count, 0)
        self.assertEqual(present_advisory_count, SRPM_UNSIGNED_FIXTURE_ADVISORY_COUNT)

    def test_sync_skip_srpm_ignored_on_mirror(self):
        """SRPMs are not skipped if the repo is synced in mirror mode."""  # noqa
        # TODO: This might change with https://pulp.plan.io/issues/9231
        body = gen_rpm_remote(SRPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)
        repo = self.repo_api.create(gen_repo())
        self.sync(repository=repo, remote=remote, skip_types=["srpm"], mirror=True)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repo = self.repo_api.read(repo.pulp_href)
        present_package_count = len(get_content(repo.to_dict())[PULP_TYPE_PACKAGE])
        present_advisory_count = len(get_content(repo.to_dict())[PULP_TYPE_ADVISORY])
        self.assertEqual(present_package_count, SRPM_UNSIGNED_FIXTURE_PACKAGE_COUNT)
        self.assertEqual(present_advisory_count, SRPM_UNSIGNED_FIXTURE_ADVISORY_COUNT)

    def test_sha_checksum(self):
        """Test that we can sync a repo using SHA as a checksum."""
        body = gen_rpm_remote(RPM_SHA_FIXTURE_URL, policy="immediate")
        remote = self.remote_api.create(body)
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.do_test(repository=repo, remote=remote)

    def do_test(self, repository=None, remote=None, mirror=False):
        """Sync a repository.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
            mirror (bool): Whether to use mirror-mode during the sync
        Returns (tuple):
            tuple of instances of
            pulp_rpm.app.models.repository.RpmRepository, pulp_rpm.app.models.repository.RpmRemote
        """
        if repository:
            repo = self.repo_api.read(repository.pulp_href)
        else:
            repo = self.repo_api.create(gen_repo())
            self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")

        if not remote:
            body = gen_rpm_remote()
            remote = self.remote_api.create(body)
        else:
            remote = self.remote_api.read(remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=mirror)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        return self.repo_api.read(repo.pulp_href), self.remote_api.read(remote.pulp_href)

    def sync(self, repository=None, remote=None, optimize=True, mirror=False, skip_types=None):
        """Sync a repository and return the task.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
        Returns (list):
            list of the ProgressReport objects created from this sync
        """
        if skip_types is None:
            skip_types = []
        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href, optimize=optimize, mirror=mirror, skip_types=skip_types
        )
        sync_response = self.repo_api.sync(repository.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        return progress_reports(sync_response.task)

    def optimize_report(self, progress_reports=[]):
        """Return whether an optimize progress report exists."""
        for report in progress_reports:
            if report.code == "sync.was_skipped":
                return True
        return False

    def test_one_nevra_two_locations_and_checksums(self):
        """Sync a repository known to have one nevra, in two locations, with different content.

        While 'odd', this is a real-world occurrence.
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=CENTOS7_OPSTOOLS, policy="on_demand")
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

    @unittest.skip("Works fine but takes 180s to run - skip unless specifically needed.")
    def test_requires_urlencoded_paths(self):
        """Sync a repository known to FAIL when an RPM has non-urlencoded characters in its path.

        See Amazon, java-11-amazon-corretto-javadoc-11.0.8+10-1.amzn2.x86_64.rpm, and
        issue https://pulp.plan.io/issues/8875 .

        NOTE: testing that this 'works' requires testing against a webserver that does
        whatever-it-is that Amazon's backend is doing. That's why it requires the external repo.
        The rest of the pulp_rpm test-suite is showing us that the code for this fix isn't
        breaking anyone *else*...
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=AMAZON_MIRROR, policy="on_demand")
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=False)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)


class InvalidSyncConfigTestCase(PulpTestCase):
    """Test syncing with invalid configurations."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()
        cls.cli_client = cli.Client(config.get_config())
        cls.md5_allowed = "md5" in get_pulp_setting(cls.cli_client, "ALLOWED_CONTENT_CHECKSUMS")

    def test_invalid_url(self):
        """Sync a repository using a remote url that does not exist.

        Test that we get a task failure. See :meth:`do_test`.
        """
        error = self.do_test("http://i-am-an-invalid-url.com/invalid/")
        self.assertIsNotNone(error)

    def test_invalid_rpm_content(self):
        """Sync a repository using an invalid plugin_content repository.

        Assert that an exception is raised, and that error message has
        keywords related to the reason of the failure. See :meth:`do_test`.
        """
        error = self.do_test(RPM_INVALID_FIXTURE_URL)
        for key in ("missing", "filelists.xml"):
            self.assertIn(key, error)

    @skip_if(bool, "md5_allowed", True)
    def test_sync_metadata_with_unsupported_checksum_type(self):
        """
        Sync an RPM repository with an unsupported checksum (md5).

        This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
        """
        error = self.do_test(RPM_MD5_REPO_FIXTURE_URL)

        self.assertIn(
            "does not contain at least one trusted hasher which is specified in "
            "'ALLOWED_CONTENT_CHECKSUMS'",
            error,
        )

    @unittest.skip(
        "Needs a repo where an unacceptable checksum is used for packages, but not for metadata"
    )
    @skip_if(bool, "md5_allowed", True)
    def test_sync_packages_with_unsupported_checksum_type(self):
        """
        Sync an RPM repository with an unsupported checksum (md5) used for packages.

        This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
        """
        error = self.do_test(RPM_MD5_REPO_FIXTURE_URL)

        self.assertIn(
            "rpm-with-md5/bear-4.1-1.noarch.rpm contains forbidden checksum type",
            error,
        )

    def test_complete_mirror_with_xml_base_fails(self):
        """Test that syncing a repository that uses xml:base in mirror mode fails."""
        error = self.do_test(REPO_WITH_XML_BASE_URL, sync_policy="mirror_complete")

        self.assertIn(
            "features which are incompatible with 'mirror' sync",
            error,
        )

    def test_complete_mirror_with_external_location_href_fails(self):
        """
        Test that syncing a repository that contains an external location_href fails in mirror mode.

        External location_href refers to a location_href that points outside of the repo,
        e.g. ../../Packages/blah.rpm
        """
        error = self.do_test(REPO_WITH_EXTERNAL_LOCATION_HREF_URL, sync_policy="mirror_complete")

        self.assertIn(
            "features which are incompatible with 'mirror' sync",
            error,
        )

    def test_complete_mirror_with_delta_metadata_fails(self):
        """
        Test that syncing a repository that contains prestodelta metadata fails in mirror mode.

        Otherwise we would be mirroring the metadata without mirroring the DRPM packages.
        """
        error = self.do_test(DRPM_UNSIGNED_FIXTURE_URL, sync_policy="mirror_complete")

        self.assertIn(
            "features which are incompatible with 'mirror' sync",
            error,
        )

    def test_mirror_and_sync_policy_provided_simultaneously_fails(self):
        """
        Test that syncing fails if both the "mirror" and "sync_policy" params are provided.
        """
        from pulpcore.client.pulp_rpm.exceptions import ApiException

        with self.assertRaises(ApiException):
            self.do_test(DRPM_UNSIGNED_FIXTURE_URL, sync_policy="mirror_complete", mirror=True)

    def do_test(self, url, **sync_kwargs):
        """Sync a repository given ``url`` on the remote."""
        repo_api = RepositoriesRpmApi(self.client)
        remote_api = RemotesRpmApi(self.client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=url, policy="on_demand")
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, **sync_kwargs)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)

        with self.assertRaises(PulpTaskError) as ctx:
            monitor_task(sync_response.task)

        return ctx.exception.task.error["description"]


class SyncedMetadataTestCase(PulpTestCase):
    """Sync a repository and validate that the package metadata is correct."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.publications = PublicationsRpmApi(cls.client)

    def setUp(self):
        """Setup to run before every test."""
        delete_orphans()

    def test_core_metadata(self):
        """Test that the metadata returned by the Pulp API post-sync matches what we expect.

        Do the following:

        1. Sync a repo.
        2. Query package metadata from the API.
        3. Match it against the metadata that we expect to be there.
        """
        body = gen_rpm_remote(RPM_COMPLEX_FIXTURE_URL, policy="on_demand")
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_setup(remote=remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        packages_api = ContentPackagesApi(self.client)

        package = packages_api.list(name=RPM_COMPLEX_PACKAGE_DATA["name"]).results[0]
        package = package.to_dict()
        # delete pulp-specific metadata
        package.pop("pulp_href")
        package.pop("pulp_created")

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
        diff = dictdiffer.diff(package, RPM_COMPLEX_PACKAGE_DATA, ignore={"time_file"})
        self.assertListEqual(list(diff), [], list(diff))

    def test_treeinfo_metadata(self):
        """Test that the metadata returned by the Pulp API post-sync matches what we expect.

        Do the following:

        1. Sync a repo.
        2. Query treeinfo metadata from the API.
        3. Match it against the metadata that we expect to be there.
        """
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL, policy="on_demand")
        remote = self.remote_api.create(body)

        # sync
        repo, remote = self.do_setup(remote=remote)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        distribution_trees_api = ContentDistributionTreesApi(self.client)

        distribution_tree = distribution_trees_api.list().results[0]
        distribution_tree = distribution_tree.to_dict()
        # delete pulp-specific metadata
        distribution_tree.pop("pulp_href")

        # sort kickstart metadata so that we can compare the dicts properly
        for d in [distribution_tree, RPM_KICKSTART_DATA]:
            d["addons"] = sorted(d["addons"], key=lambda x: x["addon_id"])
            d["images"] = sorted(d["images"], key=lambda x: x["path"])
            d["checksums"] = sorted(d["checksums"], key=lambda x: x["path"])
            d["variants"] = sorted(d["variants"], key=lambda x: x["variant_id"])

        diff = dictdiffer.diff(distribution_tree, RPM_KICKSTART_DATA)
        self.assertListEqual(list(diff), [], list(diff))

    def do_setup(self, repository=None, remote=None, mirror=False):
        """Sync a repository.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
            mirror (bool): Whether to use mirror-mode during the sync
        Returns (tuple):
            tuple of instances of
            pulp_rpm.app.models.repository.RpmRepository, pulp_rpm.app.models.repository.RpmRemote
        """
        if repository:
            repo = self.repo_api.read(repository.pulp_href)
        else:
            repo = self.repo_api.create(gen_repo())
            self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")

        if not remote:
            body = gen_rpm_remote()
            remote = self.remote_api.create(body)
        else:
            remote = self.remote_api.read(remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=mirror)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        return self.repo_api.read(repo.pulp_href), self.remote_api.read(remote.pulp_href)


class AdditiveModeTestCase(PulpTestCase):
    """Test of additive mode.

    1. Create repository, remote and sync it
    2. Create remote with different set of content
    3. Re-sync and check if new content was added and is present with old one
    """

    def test_all(self):
        """Test of additive mode."""
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)

        # 1. create repo, remote and sync them
        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 2. create another remote and re-sync
        body = gen_rpm_remote(url=SRPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, sync_policy="additive")
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 3. Check content counts
        repo = repo_api.read(repo.pulp_href)
        present_package_count = len(get_content(repo.to_dict())[PULP_TYPE_PACKAGE])
        present_advisory_count = len(get_content(repo.to_dict())[PULP_TYPE_ADVISORY])
        self.assertEqual(
            RPM_PACKAGE_COUNT + SRPM_UNSIGNED_FIXTURE_PACKAGE_COUNT, present_package_count
        )
        self.assertEqual(
            RPM_ADVISORY_COUNT + SRPM_UNSIGNED_FIXTURE_ADVISORY_COUNT, present_advisory_count
        )


class MirrorModeTestCase(PulpTestCase):
    """Test of sync with mirror mode."""

    def test_mirror_complete(self):
        """Test complete (metadata) mirroring."""
        self.do_test("mirror_complete")

    def test_mirror_content_only(self):
        """Test content-only mirroring."""
        self.do_test("mirror_content_only")

    def do_test(self, sync_policy):
        """Test of mirror mode."""
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)
        publications_api = PublicationsRpmApi(client)

        # 1. create repo, remote and sync them
        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)
        self.assertEqual(publications_api.list().count, 0)

        body = gen_rpm_remote(url=SRPM_UNSIGNED_FIXTURE_URL, policy="on_demand")
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)

        # 2. check that one repository version was created w/ no publications
        self.assertEqual(len(task.created_resources), 1)
        self.assertEqual(publications_api.list().count, 0)

        # 3. create another remote and re-sync
        body = gen_rpm_remote(url=RPM_SIGNED_FIXTURE_URL)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href, sync_policy=sync_policy
        )
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)

        # 4. check that one publication was created w/ no repository versions, and only
        # the new content is present
        repo = repo_api.read(repo.pulp_href)
        self.assertDictEqual(RPM_FIXTURE_SUMMARY, get_content_summary(repo.to_dict()))
        if sync_policy == "mirror_complete":
            self.assertEqual(publications_api.list().count, 1)
            self.assertEqual(len(task.created_resources), 2)
        else:
            self.assertEqual(len(task.created_resources), 1)
