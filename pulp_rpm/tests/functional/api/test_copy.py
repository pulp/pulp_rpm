# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_added_content_summary,
    get_content_summary,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_ADVISORY_CONTENT_NAME,
    RPM_FIXTURE_SUMMARY,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote, rpm_copy
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicCopyTestCase(unittest.TestCase):
    """Sync repositories with the rpm plugin."""

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

        rpm_copy(self.cfg, source_repo, dest_repo, criteria)
        dest_repo = self.client.get(dest_repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(dest_repo), expected_results)
        self.assertDictEqual(
            get_added_content_summary(dest_repo), expected_results,
        )

    def test_copy_all(self):
        """Test copying all the content from one repo to another."""
        criteria = {}
        results = RPM_FIXTURE_SUMMARY
        self._do_test(criteria, results)

    # def test_copy_by_href(self):
    #     criteria = {}
    #     results = {}
    #     self._do_test(criteria, results)

    def test_copy_by_advisory_id(self):
        """Test copying an advisory by its id."""
        criteria = {
            'advisory': [{'id': 'RHEA-2012:0056'}]
        }
        results = {
            RPM_ADVISORY_CONTENT_NAME: 1
        }
        self._do_test(criteria, results)
