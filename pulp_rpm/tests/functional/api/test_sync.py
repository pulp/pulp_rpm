# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import os
import unittest
from random import choice

from pulp_smash import cli, config
from pulp_smash.pulp3.constants import MEDIA_PATH
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

from pulp_rpm.tests.functional.constants import (
    RPM_ADVISORY_CONTENT_NAME,
    RPM_EPEL_URL,
    RPM_FIXTURE_SUMMARY,
    RPM_INVALID_FIXTURE_URL,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_SUMMARY,
    RPM_MODULAR_FIXTURE_URL,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_PACKAGE_COUNT,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_UPDATERECORD_ID,
    RPM_UPDATED_UPDATEINFO_FIXTURE_URL,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_SIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
    monitor_task,
    progress_reports,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)


class BasicSyncTestCase(unittest.TestCase):
    """Sync a repository with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        delete_orphans(cls.cfg)

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
        if 'JENKINS_HOME' not in os.environ:
            raise unittest.SkipTest('Slow test. It should only run on Jenkins')

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
            get_added_content_summary(repo.to_dict()),
            RPM_KICKSTART_FIXTURE_SUMMARY
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
                content['name'],
                content['epoch'],
                content['version'],
                content['release'],
                content['arch'],
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
                content['name'],
                content['epoch'],
                content['version'],
                content['release'],
                content['arch'],
            ): content
            for content in get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]
        }

        for nevra in original_packages:
            with self.subTest(pkg=nevra):
                self.assertNotEqual(
                    original_packages[nevra]['pkgId'],
                    mutated_packages[nevra]['pkgId'],
                    original_packages[nevra]['pkgId'],
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
        self.assertEqual(added_content[0]['checksum_type'], 'sha512')
        self.assertEqual(removed_content[0]['checksum_type'], 'sha256')

    @unittest.skip(
        'FIXME: Enable this test after we can throw out duplicate UpdateRecords'
    )
    def test_mutated_update_records(self):
        """Sync two copies of the same UpdateRecords.

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
            content['id']: content
            for content in get_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]
        }

        body = gen_rpm_remote(RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync the repository again
        repo, remote = self.do_test(repo, remote)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertEqual(
            len(get_added_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]), 4
        )
        self.assertEqual(
            len(get_removed_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]), 4
        )

        # Test that the updateinfo have been modified.
        mutated_updaterecords = {
            content['id']: content
            for content in get_content(repo.to_dict())[RPM_ADVISORY_CONTENT_NAME]
        }

        self.assertNotEqual(mutated_updaterecords, original_updaterecords)
        self.assertEqual(
            mutated_updaterecords[RPM_UPDATERECORD_ID]['description'],
            'Updated Gorilla_Erratum and the updated date contains timezone',
            mutated_updaterecords[RPM_UPDATERECORD_ID],
        )

    def test_file_decriptors(self):
        """Test whether file descriptors are closed properly.

        This test targets the following issue:

        `Pulp #4073 <https://pulp.plan.io/issues/4073>`_

        Do the following:

        1. Check if 'lsof' is installed. If it is not, skip this test.
        2. Create and sync a repo.
        3. Run the 'lsof' command to verify that files in the
           path ``/var/lib/pulp/`` are closed after the sync.
        4. Assert that issued command returns `0` opened files.
        """
        cli_client = cli.Client(self.cfg, cli.echo_handler)

        # check if 'lsof' is available
        if cli_client.run(("which", "lsof")).returncode != 0:
            raise unittest.SkipTest("lsof package is not present")

        repo_api = RepositoriesRpmApi(self.client)
        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        remote_api = RemotesRpmApi(self.client)
        remote = remote_api.create(gen_rpm_remote())
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        cmd = "lsof -t +D {}".format(MEDIA_PATH).split()
        response = cli_client.run(cmd).stdout
        self.assertEqual(len(response), 0, response)

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
        body['url'] = RPM_RICH_WEAK_FIXTURE_URL
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

    def sync(self, repository=None, remote=None, optimize=True):
        """Sync a repository and return the task.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
        Returns (list):
            list of the ProgressReport objects created from this sync
        """
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, optimize=optimize)
        sync_response = self.repo_api.sync(repository.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        return progress_reports(sync_response.task)

    def optimize_report(self, progress_reports=[]):
        """Return whether an optimize progress report exists."""
        for report in progress_reports:
            if report.message == "Optimizing Sync":
                return True
        return False


class SyncInvalidTestCase(unittest.TestCase):
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
        return monitor_task(sync_response.task)
