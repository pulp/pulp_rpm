# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content,
    get_content,
    get_content_summary,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_COUNT,
    RPM_FIXTURE_CONTENT_SUMMARY,
    RPM_REMOTE_PATH,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_UPDATED_UPDATEINFO_FIXTURE_URL,
    RPM_UPDATERECORD_ID,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicSyncRpmRepoTestCase(unittest.TestCase):
    """Sync repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()

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
        5. Assert that the correct number of units were added and are present in the repo.
        6. Sync the remote one more time.
        7. Assert that repository version is different from the previous one.
        8. Assert that the same number of are present and that no units were added.
        """
        client = api.Client(self.cfg, api.json_handler)

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote()
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])

        # Check that we have the correct content counts.
        self.assertIsNotNone(repo['_latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_CONTENT_SUMMARY)
        self.assertEqual(len(get_added_content(repo)), RPM_FIXTURE_COUNT)

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])

        # Check that nothing has changed since the last sync.
        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_CONTENT_SUMMARY)
        self.assertEqual(len(get_added_content(repo)), 0)


@unittest.skip("FIXME: Enable this test after we can throw out duplicate Errata")
class SyncMutatedUpdateRecordTestCase(unittest.TestCase):
    """Sync a new Erratum with the same ID."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()

    def test_all(self):
        """Sync repositories with the rpm plugin.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository and a remote.
        2. Sync the remote.
        3. Assert that the content summary matches what is expected.
        4. Create a new remote w/ using fixture containing updated errata (updaterecords with the
           ID as the existing updaterecord content, but different metadata)
        5. Sync the remote again.
        6. Assert that repository version is different from the previous one but has the same
           content summary.
        7. Assert that the updaterecords have changed since the last sync.
        """
        client = api.Client(self.cfg, api.json_handler)

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        # Create a remote with the unsigned RPM fixture url.
        # We need to use the unsigned fixture because the one used down below has unsigned RPMs.
        # Signed and unsigned units have different hashes, so they're seen as different units.
        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_CONTENT_SUMMARY)

        # Save a copy of the original updateinfo
        original_updaterecords = {
            content['errata_id']: content for content in get_content(repo)
            if content['type'] == 'update'
        }

        # Create a remote with a different test fixture, one containing mutated updateinfo.
        body = gen_rpm_remote(url=RPM_UPDATED_UPDATEINFO_FIXTURE_URL)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository again.
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_CONTENT_SUMMARY)
        self.assertEqual(len(get_added_content(repo)), 0)

        # Test that the updateinfo have been modified.
        mutated_updaterecords = {
            content['errata_id']: content for content in get_content(repo)
            if content['type'] == 'update'
        }

        self.assertNotEqual(mutated_updaterecords, original_updaterecords)
        self.assertEqual(mutated_updaterecords[RPM_UPDATERECORD_ID]['description'],
                         "Updated Gorilla_Erratum and the updated date contains timezone")
