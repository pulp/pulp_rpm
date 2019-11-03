# coding=utf-8
"""Tests for Pulp`s download policies."""
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
    RPM_FIXTURE_SUMMARY,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_remote,
    publish,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SyncPublishDownloadPolicyTestCase(unittest.TestCase):
    """Sync/Publish a repository with different download policies.

    This test targets the following issues:

    `Pulp #4126 <https://pulp.plan.io/issues/4126>`_
    `Pulp #4213 <https://pulp.plan.io/issues/4213>`_
    `Pulp #4418 <https://pulp.plan.io/issues/4418>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables, and clean orphan units."""
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.client = api.Client(cls.cfg, api.page_handler)

    def test_on_demand(self):
        """Sync/Publish with ``on_demand`` download policy.

        See :meth:`do_sync`.
        See :meth:`do_publish`.
        """
        self.do_sync('on_demand')
        self.do_publish('on_demand')

    def test_streamed(self):
        """Sync/Publish with ``streamend`` download policy.

        See :meth:`do_sync`.
        See :meth:`do_publish`.
        """
        self.do_sync('streamed')
        self.do_publish('streamed')

    def do_sync(self, download_policy):
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
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(
            RPM_REMOTE_PATH,
            gen_rpm_remote(policy=download_policy)
        )
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertIsNotNone(repo['latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(
            get_added_content_summary(repo),
            RPM_FIXTURE_SUMMARY
        )

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertNotEqual(latest_version_href, repo['latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo), {})

    def do_publish(self, download_policy):
        """Publish repository synced with lazy ``download_policy``."""
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(
            RPM_REMOTE_PATH,
            gen_rpm_remote(policy=download_policy)
        )
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        publication = publish(self.cfg, repo)
        self.assertIsNotNone(publication['repository_version'], publication)
