# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import unittest

from pulp_smash import api, cli, config
from pulp_smash.pulp3.constants import MEDIA_PATH, REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content,
    get_content,
    get_added_content_summary,
    get_content_summary,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_SUMMARY,
    RPM_PACKAGE_NAME,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_REMOTE_PATH,
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
        if cli_client.run(('which', 'lsof')).returncode != 0:
            raise unittest.SkipTest('lsof package is not present')

        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        remote = self.client.post(RPM_REMOTE_PATH, gen_rpm_remote())
        self.addCleanup(self.client.delete, remote['_href'])

        sync(self.cfg, remote, repo)

        cmd = 'lsof -t +D {}'.format(MEDIA_PATH).split()
        response = cli_client.run(cmd).stdout
        self.assertEqual(len(response), 0, response)

    def test_sync(self):
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
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote()
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        # Check that we have the correct content counts.
        self.assertIsNotNone(repo['_latest_version_href'])
        self.assertDictEqual(
            get_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )
        self.assertDictEqual(
            get_added_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        # Check that nothing has changed since the last sync.
        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
        self.assertDictEqual(
            get_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )
        self.assertDictEqual(get_added_content_summary(repo), {})


@unittest.skip('FIXME: Enable this test after we can throw out duplicate Packages')
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
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        # Create a remote with the unsigned RPM fixture url.
        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])
        self.assertDictEqual(
            get_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )

        # Save a copy of the original packages.
        original_packages = {
            content['id']: content
            for content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
            if content['type'] == 'packages'
        }

        # Create a remote with a different test fixture with the same NEVRA but
        # different digests.
        body = gen_rpm_remote(url=RPM_SIGNED_FIXTURE_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        # Sync the repository again.
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])
        self.assertDictEqual(
            get_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )
        self.assertEqual(
            len(get_added_content(repo)[RPM_PACKAGE_CONTENT_NAME]),
            0
        )

        # Test that the packages have been modified.
        mutated_packages = {
            content['id']: content
            for content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
            if content['type'] == 'update'
        }

        self.assertNotEqual(mutated_packages, original_packages)
        self.assertNotEqual(
            mutated_packages[RPM_PACKAGE_NAME]['pkgId'],
            original_packages[RPM_PACKAGE_NAME]['pkgId']
        )


@unittest.skip('FIXME: Enable this test after we can throw out duplicate UpdateRecords')
class SyncMutatedUpdateRecordTestCase(unittest.TestCase):
    """Sync a new Erratum with the same ID."""

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

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        # Create a remote with the unsigned RPM fixture url.
        # We need to use the unsigned fixture because the one used down below
        # has unsigned RPMs. Signed and unsigned units have different hashes,
        # so they're seen as different units.
        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])
        self.assertDictEqual(
            get_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )

        # Save a copy of the original updateinfo
        original_updaterecords = {
            content['id']: content
            for content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
            if content['type'] == 'update'
        }

        # Create a remote with a different test fixture, one containing mutated
        # updateinfo.
        body = gen_rpm_remote(url=RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository again.
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])
        self.assertDictEqual(
            get_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )
        self.assertEqual(
            len(get_added_content(repo)[RPM_PACKAGE_CONTENT_NAME]),
            0
        )

        # Test that the updateinfo have been modified.
        mutated_updaterecords = {
            content['id']: content
            for content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
            if content['type'] == 'update'
        }

        self.assertNotEqual(mutated_updaterecords, original_updaterecords)
        self.assertEqual(
            mutated_updaterecords[RPM_UPDATERECORD_ID]['description'],
            'Updated Gorilla_Erratum and the updated date contains timezone',
            mutated_updaterecords[RPM_UPDATERECORD_ID]
        )
