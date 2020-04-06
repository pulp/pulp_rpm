# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_added_content_summary,
    get_content,
    get_content_summary,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    KICKSTART_CONTENT_PATH,
    RPM_KICKSTART_CONTENT_NAME,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    RPM_UNSIGNED_FIXTURE_URL,
    UPDATERECORD_CONTENT_PATH,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote, rpm_copy
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicCopyTestCase(unittest.TestCase):
    """Copy units between repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        delete_orphans(cls.cfg)

    def _setup_repos(self, remote_url=RPM_UNSIGNED_FIXTURE_URL, summary=RPM_FIXTURE_SUMMARY):
        """Prepare for a copy test by creating two repos and syncing.

        Do the following:

        1. Create two repositories and a remote.
        2. Sync the remote.
        3. Assert that repository version is not None.
        4. Assert that the correct number of units were added and are present in the repo.
        """
        source_repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, source_repo['pulp_href'])

        dest_repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, dest_repo['pulp_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote(url=remote_url)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertEqual(source_repo["latest_version_href"],
                         f"{source_repo['pulp_href']}versions/0/")
        sync(self.cfg, remote, source_repo)
        source_repo = self.client.get(source_repo['pulp_href'])

        for kickstart_content in get_content(source_repo).get(RPM_KICKSTART_CONTENT_NAME, []):
            self.addCleanup(self.client.delete, kickstart_content['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(source_repo), summary)
        self.assertDictEqual(
            get_added_content_summary(source_repo), summary
        )

        return source_repo, dest_repo

    def test_copy_all(self):
        """Test copying all the content from one repo to another."""
        source_repo, dest_repo = self._setup_repos()
        results = RPM_FIXTURE_SUMMARY
        config = [{
            'source_repo_version': source_repo['latest_version_href'],
            'dest_repo': dest_repo['pulp_href'],
        }]

        rpm_copy(self.cfg, config)
        dest_repo = self.client.get(dest_repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(dest_repo), results)
        self.assertDictEqual(
            get_added_content_summary(dest_repo), results,
        )

    def test_invalid_config(self):
        """Test invalid config."""
        source_repo, dest_repo = self._setup_repos()

        with self.assertRaises(HTTPError):
            # no list
            config = {
                'source_repo_version': source_repo['latest_version_href'],
                'dest_repo': dest_repo['pulp_href'],
            }
            rpm_copy(self.cfg, config)

        with self.assertRaises(HTTPError):
            good = {
                'source_repo_version': source_repo['latest_version_href'],
                'dest_repo': dest_repo['pulp_href']
            }
            bad = {
                'source_repo_version': source_repo['latest_version_href']
            }
            config = [good, bad]
            rpm_copy(self.cfg, config)

        with self.assertRaises(HTTPError):
            config = [{
                'source_repo': source_repo['latest_version_href'],
                'dest_repo': dest_repo['pulp_href'],
            }]
            rpm_copy(self.cfg, config)

    def test_content(self):
        """Test the content parameter."""
        source_repo, dest_repo = self._setup_repos()
        latest_href = source_repo["latest_version_href"]

        content = self.client.get(f"{UPDATERECORD_CONTENT_PATH}?repository_version={latest_href}")
        content_to_copy = (content["results"][0]["pulp_href"], content["results"][1]["pulp_href"])

        config = [{
            'source_repo_version': latest_href,
            'dest_repo': dest_repo['pulp_href'],
            'content': content_to_copy
        }]

        rpm_copy(self.cfg, config)

        dest_repo = self.client.get(dest_repo['pulp_href'])
        latest_href = dest_repo["latest_version_href"]
        dc = self.client.get(f"{UPDATERECORD_CONTENT_PATH}?repository_version={latest_href}")
        dest_content = [c["pulp_href"] for c in dc["results"]]

        self.assertEqual(sorted(content_to_copy), sorted(dest_content))

    def test_kickstart_copy_all(self):
        """Test copying all the content from one repo to another."""
        source_repo, dest_repo = self._setup_repos(
            remote_url=RPM_KICKSTART_FIXTURE_URL,
            summary=RPM_KICKSTART_FIXTURE_SUMMARY,
        )
        results = RPM_KICKSTART_FIXTURE_SUMMARY
        config = [{
            'source_repo_version': source_repo['latest_version_href'],
            'dest_repo': dest_repo['pulp_href'],
        }]

        rpm_copy(self.cfg, config)
        dest_repo = self.client.get(dest_repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(dest_repo), results)
        self.assertDictEqual(
            get_added_content_summary(dest_repo), results,
        )

    def test_kickstart_content(self):
        """Test the content parameter."""
        source_repo, dest_repo = self._setup_repos(
            remote_url=RPM_KICKSTART_FIXTURE_URL,
            summary=RPM_KICKSTART_FIXTURE_SUMMARY,
        )
        latest_href = source_repo["latest_version_href"]

        content = self.client.get(f"{KICKSTART_CONTENT_PATH}?repository_version={latest_href}")
        content_to_copy = [content["results"][0]["pulp_href"]]

        config = [{
            'source_repo_version': latest_href,
            'dest_repo': dest_repo['pulp_href'],
            'content': content_to_copy
        }]

        rpm_copy(self.cfg, config)

        dest_repo = self.client.get(dest_repo['pulp_href'])
        latest_href = dest_repo["latest_version_href"]
        dc = self.client.get(f"{KICKSTART_CONTENT_PATH}?repository_version={latest_href}")
        dest_content = [c["pulp_href"] for c in dc["results"]]

        self.assertEqual(content_to_copy, dest_content)


class DependencySolvingTestCase(unittest.TestCase):
    """Copy units between repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        delete_orphans(cls.cfg)

    def _do_test(self, criteria, expected_results):
        """Test copying content units with the RPM plugin.

        Do the following:

        1. Create two repositories and a remote.
        2. Sync the remote.
        3. Assert that repository version is not None.
        4. Assert that the correct number of units were added and are present in the repo.
        5. Use the RPM copy API to units from the repo to the empty repo.
        7. Assert that the correct number of units were added and are present in the dest repo.
        """
        source_repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, source_repo['pulp_href'])

        dest_repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, dest_repo['pulp_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote()
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertEqual(source_repo["latest_version_href"],
                         f"{source_repo['pulp_href']}versions/0/")
        sync(self.cfg, remote, source_repo)
        source_repo = self.client.get(source_repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(source_repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(
            get_added_content_summary(source_repo), RPM_FIXTURE_SUMMARY
        )

        rpm_copy(self.cfg, source_repo, dest_repo, criteria, recursive=True)
        dest_repo = self.client.get(dest_repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(dest_repo), expected_results)
        self.assertDictEqual(
            get_added_content_summary(dest_repo), expected_results,
        )
