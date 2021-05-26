"""Tests that sync rpm plugin repositories."""
import os
import unittest
from random import choice

from django.utils.dateparse import parse_datetime

from pulp_smash import cli, config
from pulp_smash.pulp3.bindings import PulpTaskError, PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_added_content,
    get_content,
    get_content_summary,
    get_removed_content,
    delete_orphans,
    modify_repo,
)
from pulp_smash.utils import get_pulp_setting

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_ADVISORY,
    PULP_TYPE_MODULEMD,
    PULP_TYPE_PACKAGE,
    PULP_TYPE_REPOMETADATA,
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
    RPM_FIXTURE_SUMMARY,
    RPM_INVALID_FIXTURE_URL,
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
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)


class BasicSyncTestCase(PulpTestCase):
    """Sync a repository with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.cli_client = cli.Client(cls.cfg)
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        delete_orphans(cls.cfg)
        cls.md5_allowed = "md5" in get_pulp_setting(cls.cli_client, "ALLOWED_CONTENT_CHECKSUMS")

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

    def test_sync_from_valid_mirror_list_feed(self):
        """Sync RPM content from a mirror list feed which contains a valid remote URL."""
        remote = self.remote_api.create(gen_rpm_remote(RPM_MIRROR_LIST_GOOD_FIXTURE_URL))
        repo, remote = self.do_test(remote=remote)

        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

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
            self.assertEqual(
                exc.task.to_dict()["error"]["description"], "An invalid remote URL was provided."
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

    def test_kickstarter(self):
        """Sync repositories with the rpm plugin.

        This test targets the following issue:

        `Pulp #5202 <https://pulp.plan.io/issues/5202>`_

        In order to sync a repository a remote has to be associated within
        this repository.

        Do the following:

        1. Create a remote.
        2. Sync the remote. (repo will be created automatically)
        3. Assert that the correct number of units were added and are present
           in the repo.
        4. Sync the remote one more time.
        5. Assert that repository version is the same the previous one.
        6. Assert that the same number of packages are present.
        """
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL)
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

    def test_kickstarter_on_demand(self):
        """Sync repositories with the rpm plugin.

        This test targets the following issue:

        `Pulp #5202 <https://pulp.plan.io/issues/5202>`_

        In order to sync a repository a remote has to be associated within
        this repository.

        Do the following:

        1. Create a remote.
        2. Sync the remote. (repo will be created automatically)
        3. Assert that the correct number of units were added and are present
           in the repo.
        4. Sync the remote one more time.
        5. Assert that repository version is the same the previous one.
        6. Assert that the same number of packages are present.
        """
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL, policy="on_demand")
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
        body = gen_rpm_remote(RPM_UNSIGNED_FIXTURE_URL)
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
            "Incoming and existing advisories have the same id but different "
            "timestamps and non-intersecting package lists. It is likely that they are from "
            "two different incompatible remote repositories. E.g. RHELX-repo and "
            "RHELY-debuginfo repo. Ensure that you are adding content for the compatible "
            "repositories. Advisory id: {}".format(RPM_ADVISORY_TEST_ID)
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

    def do_test(self, repository=None, remote=None):
        """Sync a repository.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
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

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
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
            if report.message == "Optimizing Sync":
                return True
        return False

    @skip_if(bool, "md5_allowed", True)
    def test_sync_packages_with_unsupported_checksum_type(self):
        """
        Sync an RPM repository with an unsupported checksum (md5).

        This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
        """
        # 1. create repo and remote
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(policy="on_demand", url=RPM_MD5_REPO_FIXTURE_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # 2. Sync it
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        with self.assertRaises(PulpTaskError) as ctx:
            monitor_task(sync_response.task)

        self.assertIn(
            "rpm-with-md5/bear-4.1-1.noarch.rpm contains forbidden checksum type",
            ctx.exception.task.error["description"],
        )


class SyncInvalidTestCase(PulpTestCase):
    """Sync a repository with a given url on the remote."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()

    def test_invalid_url(self):
        """Sync a repository using a remote url that does not exist.

        Test that we get a task failure. See :meth:`do_test`.
        """
        task = self.do_test("http://i-am-an-invalid-url.com/invalid/")
        self.assertIsNotNone(task["error"]["description"])

    def test_invalid_rpm_content(self):
        """Sync a repository using an invalid plugin_content repository.

        Assert that an exception is raised, and that error message has
        keywords related to the reason of the failure. See :meth:`do_test`.
        """
        task = self.do_test(RPM_INVALID_FIXTURE_URL)
        for key in ("missing", "filelists.xml"):
            self.assertIn(key, task["error"]["description"])

    def do_test(self, url):
        """Sync a repository given ``url`` on the remote."""
        repo_api = RepositoriesRpmApi(self.client)
        remote_api = RemotesRpmApi(self.client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=url)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        try:
            task_result = monitor_task(sync_response.task)
        except PulpTaskError as exc:
            task_result = exc.task.to_dict()
        return task_result


class AdditiveModeTestCase(PulpTestCase):
    """Test of additive mode.

    1. Create repository, remote and sync it
    2. Create remote with different set of content
    3. Re-sync and check if new content was added and is present with old one
    """

    def test_all(self):
        """Test of addtive mode."""
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)

        # 1. create repo, remote and sync them
        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 2. create another remote and re-sync
        body = gen_rpm_remote(url=SRPM_UNSIGNED_FIXTURE_URL)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
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
    """Test of sync with mirror mode.

    1. Create repository, remote and sync it
    2. Create another remote
    3. Re-sync and check if only new content is present in repository
    """

    def test_all(self):
        """Test of mirror mode."""
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)

        # 1. create repo, remote and sync them
        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=SRPM_UNSIGNED_FIXTURE_URL)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 2. create another remote and re-sync
        body = gen_rpm_remote(url=RPM_SIGNED_FIXTURE_URL)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=True)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 3. Check that only new content is present
        repo = repo_api.read(repo.pulp_href)
        self.assertDictEqual(RPM_FIXTURE_SUMMARY, get_content_summary(repo.to_dict()))
