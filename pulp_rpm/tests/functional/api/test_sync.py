# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import os
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config
from pulp_smash.pulp3.constants import MEDIA_PATH, ARTIFACTS_PATH
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_added_content,
    get_added_content_summary,
    get_content,
    get_content_summary,
    get_removed_content,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_ADVISORY_CONTENT_NAME,
    RPM_EPEL_URL,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_CONTENT_NAME,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_SUMMARY,
    RPM_MODULAR_FIXTURE_URL,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_PACKAGE_COUNT,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    RPM_SHA512_FIXTURE_URL,
    RPM_SIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_UPDATED_UPDATEINFO_FIXTURE_URL,
    RPM_UPDATERECORD_ID,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicSyncTestCase(unittest.TestCase):
    """Sync repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        delete_orphans(cls.cfg)

    def test_rpm(self):
        """Sync repositories with the rpm plugin.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository and a remote.
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
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote()
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertIsNotNone(repo['latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(
            get_added_content_summary(repo), RPM_FIXTURE_SUMMARY
        )

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        # Check that nothing has changed since the last sync.
        self.assertNotEqual(latest_version_href, repo['latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo), {})


class KickstartSyncTestCase(unittest.TestCase):
    """Sync repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        delete_orphans(cls.cfg)

    def test_rpm_kickstart(self):
        """Sync repositories with the rpm plugin.

        This test targets the following issue:


        `Pulp #5202 <https://pulp.plan.io/issues/5202>`_

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository and a remote.
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
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote(url=RPM_KICKSTART_FIXTURE_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])
        for kickstart_content in get_content(repo)[RPM_KICKSTART_CONTENT_NAME]:
            self.addCleanup(self.client.delete, kickstart_content['pulp_href'])

        # Check that we have the correct content counts.
        self.assertIsNotNone(repo['latest_version_href'])

        self.assertDictEqual(
            get_content_summary(repo), RPM_KICKSTART_FIXTURE_SUMMARY
        )
        self.assertDictEqual(
            get_added_content_summary(repo), RPM_KICKSTART_FIXTURE_SUMMARY
        )

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        artifacts = self.client.get(ARTIFACTS_PATH)
        self.assertEqual(artifacts['count'], 3, artifacts)

        # Check that nothing has changed since the last sync.
        self.assertNotEqual(latest_version_href, repo['latest_version_href'])
        self.assertDictEqual(
            get_content_summary(repo), RPM_KICKSTART_FIXTURE_SUMMARY
        )
        self.assertDictEqual(get_added_content_summary(repo), {})

    def test_rpm_kickstart_on_demand(self):
        """Sync repositories with the rpm plugin.

        This test targets the following issue:


        `Pulp #5202 <https://pulp.plan.io/issues/5202>`_

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository and a remote.
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
        delete_orphans(self.cfg)
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote(
            url=RPM_KICKSTART_FIXTURE_URL, policy='on_demand'
        )
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])
        for kickstart_content in get_content(repo)[RPM_KICKSTART_CONTENT_NAME]:
            self.addCleanup(self.client.delete, kickstart_content['pulp_href'])

        # Check that we have the correct content counts.
        self.assertIsNotNone(repo['latest_version_href'])

        self.assertDictEqual(
            get_content_summary(repo), RPM_KICKSTART_FIXTURE_SUMMARY
        )
        self.assertDictEqual(
            get_added_content_summary(repo), RPM_KICKSTART_FIXTURE_SUMMARY
        )

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        artifacts = self.client.get(ARTIFACTS_PATH)
        self.assertEqual(artifacts['count'], 0, artifacts)

        # Check that nothing has changed since the last sync.
        self.assertNotEqual(latest_version_href, repo['latest_version_href'])
        self.assertDictEqual(
            get_content_summary(repo), RPM_KICKSTART_FIXTURE_SUMMARY
        )
        self.assertDictEqual(get_added_content_summary(repo), {})


class FileDescriptorsTestCase(unittest.TestCase):
    """Test whether file descriptors are closed properly after a sync."""

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
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        cli_client = cli.Client(cfg, cli.echo_handler)

        # check if 'lsof' is available
        if cli_client.run(('which', 'lsof')).returncode != 0:
            raise unittest.SkipTest('lsof package is not present')

        repo = client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        remote = client.post(RPM_REMOTE_PATH, gen_rpm_remote())
        self.addCleanup(client.delete, remote['pulp_href'])

        sync(cfg, remote, repo)

        cmd = 'lsof -t +D {}'.format(MEDIA_PATH).split()
        response = cli_client.run(cmd).stdout
        self.assertEqual(len(response), 0, response)


class SyncMutatedPackagesTestCase(unittest.TestCase):
    """Sync different packages with the same NEVRA as existing packages."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Sync two copies of the same packages.

        Make sure we end up with only one copy.

        Do the following:

        1. Create a repository and a remote.
        2. Sync the remote.
        3. Assert that the content summary matches what is expected.
        4. Create a new remote w/ using fixture containing updated errata
           (packages with the same NEVRA as the existing package content, but
           different pkgId).
        5. Sync the remote again.
        6. Assert that repository version is different from the previous one
           but has the same content summary.
        7. Assert that the packages have changed since the last sync.
        """
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        # Create a remote with the unsigned RPM fixture url.
        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)

        # Save a copy of the original packages.
        original_packages = {
            (
                content['name'],
                content['epoch'],
                content['version'],
                content['release'],
                content['arch'],
            ): content
            for content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
        }

        # Create a remote with a different test fixture with the same NEVRA but
        # different digests.
        body = gen_rpm_remote(url=RPM_SIGNED_FIXTURE_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository again.
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)

        # In case of "duplicates" the most recent one is chosen, so the old
        # package is removed from and the new one is added to a repo version.
        self.assertEqual(
            len(get_added_content(repo)[RPM_PACKAGE_CONTENT_NAME]),
            RPM_PACKAGE_COUNT,
            get_added_content(repo)[RPM_PACKAGE_CONTENT_NAME],
        )
        self.assertEqual(
            len(get_removed_content(repo)[RPM_PACKAGE_CONTENT_NAME]),
            RPM_PACKAGE_COUNT,
            get_removed_content(repo)[RPM_PACKAGE_CONTENT_NAME],
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
            for content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
        }

        for nevra in original_packages:
            with self.subTest(pkg=nevra):
                self.assertNotEqual(
                    original_packages[nevra]['pkgId'],
                    mutated_packages[nevra]['pkgId'],
                    original_packages[nevra]['pkgId'],
                )


class EPELSyncTestCase(unittest.TestCase):
    """Sync large EPEL repository."""

    @classmethod
    def setUpClass(cls):
        """Skip test if the test is not running on Jenkins."""
        if 'JENKINS_HOME' not in os.environ:
            raise unittest.SkipTest('Slow test. It should only run on Jenkins')

    def test_sync_large_repo(self):
        """Sync large EPEL repository."""
        cfg = config.get_config()
        client = api.Client(cfg, api.page_handler)

        repo = client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        remote = client.post(RPM_REMOTE_PATH, gen_rpm_remote(url=RPM_EPEL_URL))
        self.addCleanup(client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(cfg, remote, repo)
        repo = client.get(repo['pulp_href'])
        content_summary = get_content_summary(repo)
        self.assertGreater(
            content_summary[RPM_PACKAGE_CONTENT_NAME], 0, content_summary
        )


@unittest.skip(
    'FIXME: Enable this test after we can throw out duplicate UpdateRecords'
)
class SyncMutatedUpdateRecordTestCase(unittest.TestCase):
    """Sync a new UpdateRecord (Advisory / Erratum) with the same ID."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()

    def test_all(self):
        """Sync two copies of the same UpdateRecords.

        Make sure we end up with only one copy.

        Do the following:

        1. Create a repository and a remote.
        2. Sync the remote.
        3. Assert that the content summary matches what is expected.
        4. Create a new remote w/ using fixture containing updated errata
           (updaterecords with the ID as the existing updaterecord content, but
           different metadata).
        5. Sync the remote again.
        6. Assert that repository version is different from the previous one
           but has the same content summary.
        7. Assert that the updaterecords have changed since the last sync.
        """
        client = api.Client(self.cfg, api.json_handler)

        repo = client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        # Create a remote with the unsigned RPM fixture url.
        # We need to use the unsigned fixture because the one used down below
        # has unsigned RPMs. Signed and unsigned units have different hashes,
        # so they're seen as different units.
        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = client.get(repo['pulp_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)

        # Save a copy of the original updateinfo
        original_updaterecords = {
            content['id']: content
            for content in get_content(repo)[RPM_ADVISORY_CONTENT_NAME]
        }

        # Create a remote with a different test fixture, one containing mutated
        # updateinfo.
        body = gen_rpm_remote(url=RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['pulp_href'])

        # Sync the repository again.
        sync(self.cfg, remote, repo)
        repo = client.get(repo['pulp_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertEqual(
            len(get_added_content(repo)[RPM_ADVISORY_CONTENT_NAME]), 4
        )
        self.assertEqual(
            len(get_removed_content(repo)[RPM_ADVISORY_CONTENT_NAME]), 4
        )

        # Test that the updateinfo have been modified.
        mutated_updaterecords = {
            content['id']: content
            for content in get_content(repo)[RPM_ADVISORY_CONTENT_NAME]
        }

        self.assertNotEqual(mutated_updaterecords, original_updaterecords)
        self.assertEqual(
            mutated_updaterecords[RPM_UPDATERECORD_ID]['description'],
            'Updated Gorilla_Erratum and the updated date contains timezone',
            mutated_updaterecords[RPM_UPDATERECORD_ID],
        )


class SyncDiffChecksumPackagesTestCase(unittest.TestCase):
    """Syncing duplicate NEVRA with different checksums."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Sync two fixture content with same NEVRA and different checksum.

        Make sure we end up with the most recently synced content.

        Do the following:

        1. Create a repository
        2. Create two remotes with same content but different checksums.
            Sync the remotes one after the other.
               a. Sync remote with packages with SHA256: ``RPM_UNSIGNED_FIXTURE_URL``.
               b. Sync remote with packages with SHA512: ``RPM_SHA512_FIXTURE_URL``.
        3. Make sure the latest content is only kept.

        This test targets the following issues:

        * `Pulp #4297 <https://pulp.plan.io/issues/4297>`_
        * `Pulp #3954 <https://pulp.plan.io/issues/3954>`_
        """
        # Step 1
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        # Step 2.

        for body in [
            gen_rpm_remote(),
            gen_rpm_remote(url=RPM_SHA512_FIXTURE_URL),
        ]:
            remote = self.client.post(RPM_REMOTE_PATH, body)
            self.addCleanup(self.client.delete, remote['pulp_href'])
            # Sync the repository.
            sync(self.cfg, remote, repo)

        # Step 3
        repo = self.client.get(repo['pulp_href'])
        added_content = get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
        removed_content = get_removed_content(repo)[RPM_PACKAGE_CONTENT_NAME]

        # In case of "duplicates" the most recent one is chosen, so the old
        # package is removed from and the new one is added to a repo version.
        self.assertEqual(len(added_content), RPM_PACKAGE_COUNT, added_content)
        self.assertEqual(
            len(removed_content), RPM_PACKAGE_COUNT, removed_content
        )

        # Verifying whether the packages with first checksum is removed and second
        # is added.
        self.assertEqual(added_content[0]['checksum_type'], 'sha512')
        self.assertEqual(removed_content[0]['checksum_type'], 'sha256')


class ChecksumConstraintTestCase(unittest.TestCase):
    """Verify checksum constraint test case.

    Do the following:

    1. Create and sync a repo using the following
       url=RPM_REFERENCES_UPDATEINFO_URL.
    2. Create and sync a secondary repo using the following
       url=RPM_REFERENCES_UPDATEINFO_URL.
       Those urls have RPM packages with the same name.
    3. Assert that the task succeed.

    This test targets the following issue:

    * `Pulp #4170 <https://pulp.plan.io/issues/4170>`_
    * `Pulp #4255 <https://pulp.plan.io/issues/4255>`_
    """

    def test_sync(self):
        """Test duplicate content can be synced."""
        cfg = config.get_config()
        client = api.Client(cfg)

        for url in [RPM_REFERENCES_UPDATEINFO_URL, RPM_UNSIGNED_FIXTURE_URL]:
            remote = client.post(RPM_REMOTE_PATH, gen_rpm_remote(url=url))
            self.addCleanup(client.delete, remote['pulp_href'])

            repo = client.post(RPM_REPO_PATH, gen_repo())
            self.addCleanup(client.delete, repo['pulp_href'])

            client.post(
                urljoin(repo['pulp_href'], 'sync/'),
                {'remote': remote['pulp_href']},
            )
            repo = client.get(repo['pulp_href'])

            added_content_summary = get_added_content_summary(repo)
            self.assertEqual(
                added_content_summary,
                RPM_FIXTURE_SUMMARY,
                added_content_summary,
            )


class SyncModularContentTestCase(unittest.TestCase):
    """Sync RPM modular content.

    This test targets the following issue:

    * `Pulp #5408 <https://pulp.plan.io/issues/5408>`_
    """

    def test_sync_modular_repo(self):
        """Test RPM modular content can be synced."""
        cfg = config.get_config()
        client = api.Client(cfg)

        remote = client.post(
            RPM_REMOTE_PATH, gen_rpm_remote(url=RPM_MODULAR_FIXTURE_URL)
        )
        self.addCleanup(client.delete, remote['pulp_href'])

        repo = client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        sync(cfg, remote, repo)
        repo = client.get(repo['pulp_href'])

        added_content_summary = get_added_content_summary(repo)

        self.assertEqual(
            added_content_summary,
            RPM_MODULAR_FIXTURE_SUMMARY,
            added_content_summary
        )
