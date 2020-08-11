# coding=utf-8
"""Tests that verify download of content served by Pulp."""
import unittest

from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
    get_added_content_summary,
    get_content_summary,
)

from pulp_rpm.tests.functional.constants import (
    CENTOS7_URL,
    CENTOS8_APPSTREAM_URL,
    CENTOS8_BASEOS_URL,
    CENTOS8_KICKSTART_APP_URL,
    CENTOS8_KICKSTART_BASEOS_URL,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
    tasks,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    PublicationsRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
    RpmRpmPublication,
)


class SynctoSyncTestCase(unittest.TestCase):
    """Sync repositories with the rpm plugin."""

    def do_test(self, url, policy="on_demand"):
        """Verify whether content served by pulp can be synced.

        The process of publishing content is more involved in Pulp 3 than it
        was under Pulp 2. Given a repository, the process is as follows:

        1. Create a publication from the repository. (The latest repository
           version is selected if no version is specified.) A publication is a
           repository version plus metadata.
        2. Create a distribution from the publication. The distribution defines
           at which URLs a publication is available, e.g.
           ``http://example.com/content/foo/`` and
           ``http://example.com/content/bar/``.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Sync other repository using as remote url,
        the distribution base_url from the previous repository.

        """
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)
        publications = PublicationsRpmApi(client)
        distributions = DistributionsRpmApi(client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=url, policy=policy)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        # Sync a Repository
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        sync_task = tasks.read(sync_response.task)
        task_duration = sync_task.finished_at - sync_task.started_at
        waiting_time = sync_task.started_at - sync_task.pulp_created
        print("\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(),
            service=task_duration.total_seconds()
        ))
        repo = repo_api.read(repo.pulp_href)

        # Create a publication.
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task)
        publication_href = created_resources[0]
        self.addCleanup(publications.delete, publication_href)

        # Create a distribution.
        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = distributions.create(body)
        created_resources = monitor_task(distribution_response.task)
        distribution = distributions.read(created_resources[0])
        self.addCleanup(distributions.delete, distribution.pulp_href)

        # Create another repo pointing to distribution base_url
        repo2 = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo2.pulp_href)

        body = gen_rpm_remote(url=distribution.base_url, policy=policy)
        remote2 = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote2.pulp_href)

        # Sync a Repository
        repository_sync_data = RpmRepositorySyncURL(remote=remote2.pulp_href)
        sync_response = repo_api.sync(repo2.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        sync_task = tasks.read(sync_response.task)
        task_duration = sync_task.finished_at - sync_task.started_at
        waiting_time = sync_task.started_at - sync_task.pulp_created
        print("\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(),
            service=task_duration.total_seconds()
        ))
        repo2 = repo_api.read(repo2.pulp_href)

        summary = get_content_summary(repo.to_dict())
        summary2 = get_content_summary(repo2.to_dict())
        self.assertDictEqual(summary, summary2)

        added = get_added_content_summary(repo.to_dict())
        added2 = get_added_content_summary(repo2.to_dict())
        self.assertDictEqual(added, added2)

    def test_centos7_on_demand(self):
        """Sync CentOS 7."""
        self.do_test(url=CENTOS7_URL)

    def test_centos8_baseos_on_demand(self):
        """Sync CentOS 8 BaseOS."""
        self.do_test(url=CENTOS8_BASEOS_URL)

    def test_centos8_appstream_on_demand(self):
        """Sync CentOS 8 AppStream."""
        self.do_test(url=CENTOS8_APPSTREAM_URL)

    def test_centos8_kickstart_baseos_on_demand(self):
        """Kickstart Sync CentOS 8 BaseOS."""
        self.do_test(url=CENTOS8_KICKSTART_BASEOS_URL)

    def test_centos8_kickstart_appstream_on_demand(self):
        """Kickstart Sync CentOS 8 AppStream."""
        self.do_test(url=CENTOS8_KICKSTART_APP_URL)
