# coding=utf-8
"""Tests for Pulp`s download policies."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_content_summary,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_SUMMARY,
    RPM_REMOTE_PATH,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SyncDownloadPolicyTestCase(unittest.TestCase):
    """Sync a repository with different download policies.

    This test targets the following issue:

    `Pulp #4126 <https://pulp.plan.io/issues/4126>`_
    `Pulp #4213 <https://pulp.plan.io/issues/4213>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.page_handler)

    def test_on_demand(self):
        """Sync with ``on_demand`` download policy. See :meth:`do_test`."""
        self.do_test('on_demand')

    def test_streamed(self):
        """Sync with ``streamend`` download policy.  See :meth:`do_test`."""
        self.do_test('streamed')

    def do_test(self, download_policy):
        """Sync repositories with the different ``download_policy``.

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Assert that the correct number of possible units to be downloaded
           were shown.
        6. Sync the remote one more time in order to create another repository
           version.
        7. Assert that repository version is different from the previous one.
        8. Assert that the same number of units are shown, and after the
           second sync no extra units should be shown, since the same remote
           was synced again.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        remote = self.client.post(
            RPM_REMOTE_PATH, gen_rpm_remote(**{'policy': download_policy})
        )
        self.addCleanup(self.client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertIsNotNone(repo['_latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(
            get_added_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo), {})
