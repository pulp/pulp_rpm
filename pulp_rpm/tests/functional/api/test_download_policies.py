# coding=utf-8
"""Tests for Pulp`s download policies."""
from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import gen_repo, get_added_content_summary, get_content_summary

from pulp_rpm.tests.functional.constants import (
    RPM_FIXTURE_SUMMARY,
    DOWNLOAD_POLICIES,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
    skip_if,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
    RpmRpmPublication,
    PublicationsRpmApi
)


class SyncPublishDownloadPolicyTestCase(PulpTestCase):
    """Sync a repository with different download policies.

    This test targets the following issue:

    `Pulp #4126 <https://pulp.plan.io/issues/4126>`_
    `Pulp #4213 <https://pulp.plan.io/issues/4213>`_
    `Pulp #4418 <https://pulp.plan.io/issues/4418>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()
        cls.DP_ON_DEMAND = "on_demand" in DOWNLOAD_POLICIES
        cls.DP_STREAMED = "streamed" in DOWNLOAD_POLICIES

    @skip_if(bool, "DP_ON_DEMAND", False)
    def test_on_demand(self):
        """Sync with ``on_demand`` download policy. See :meth:`do_test`."""
        self.do_test("on_demand")

    @skip_if(bool, "DP_STREAMED", False)
    def test_streamed(self):
        """Sync with ``streamend`` download policy.  See :meth:`do_test`."""
        self.do_test("streamed")

    def do_test(self, download_policy):
        """Sync repositories with the different ``download_policy``.

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the remote.
        3. Assert that repository version is not None.
        4. Assert that the correct number of possible units to be downloaded
           were shown.
        5. Sync the remote one more time in order to create another repository
           version.
        6. Assert that repository version is different from the previous one.
        7. Assert that the same number of units are shown, and after the
           second sync no extra units should be shown, since the same remote
           was synced again.
        8. Publish repository synced with lazy ``download_policy``.
        """
        repo_api = RepositoriesRpmApi(self.client)
        remote_api = RemotesRpmApi(self.client)
        publications = PublicationsRpmApi(self.client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(**{"policy": download_policy})
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        # Sync the repository.
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

        # Sync the repository again.
        latest_version_href = repo.latest_version_href
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        self.assertEqual(latest_version_href, repo.latest_version_href)
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

        # Publish
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task)
        publication_href = created_resources[0]

        self.addCleanup(publications.delete, publication_href)

        publication = publications.read(publication_href)
        self.assertIsNotNone(publication.repository)
        self.assertIsNotNone(publication.repository_version)
