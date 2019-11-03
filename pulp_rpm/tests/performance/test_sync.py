# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import unittest
from datetime import datetime
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_added_content_summary,
    get_content,
    get_content_summary,
)

from pulp_rpm.tests.functional.constants import (
    RPM_KICKSTART_CONTENT_NAME,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    CENTOS7_URL,
    CENTOS8_APPSTREAM_URL,
    CENTOS8_BASEOS_URL,
    CENTOS8_KICKSTART_APP_URL,
    CENTOS8_KICKSTART_BASEOS_URL,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SyncTestCase(unittest.TestCase):
    """Sync repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        delete_orphans(cls.cfg)

    def parse_date_from_string(self, s, parse_format='%Y-%m-%dT%H:%M:%S.%fZ'):
        """Parse string to datetime object.

        :param s: str like '2018-11-18T21:03:32.493697Z'
        :param parse_format: str defaults to %Y-%m-%dT%H:%M:%S.%fZ
        :return: datetime.datetime
        """
        return datetime.strptime(s, parse_format)

    def rpm_sync(self, url=RPM_KICKSTART_FIXTURE_URL, policy='on_demand'):
        """Sync repositories with the rpm plugin.

        This test targets the following issue:
        `Pulp #5506 <https://pulp.plan.io/issues/5506>`_.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Assert that distribution_tree units were added and are present in the repo.
        """
        delete_orphans(self.cfg)
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        # Create a remote with the standard test fixture url.
        body = gen_rpm_remote(url=url, policy=policy)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        data = {"remote": remote["pulp_href"]}
        response = self.client.using_handler(api.json_handler).post(
            urljoin(repo["pulp_href"], "sync/"), data
        )
        sync_task = self.client.get(response["task"])
        created_at = self.parse_date_from_string(sync_task["pulp_created"])
        started_at = self.parse_date_from_string(sync_task["started_at"])
        finished_at = self.parse_date_from_string(sync_task["finished_at"])
        task_duration = finished_at - started_at
        waiting_time = started_at - created_at
        print("\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(),
            service=task_duration.total_seconds()
        ))

        repo = self.client.get(repo['pulp_href'])
        for kickstart_content in get_content(repo)[RPM_KICKSTART_CONTENT_NAME]:
            self.addCleanup(self.client.delete, kickstart_content['pulp_href'])

        # Check that we have the correct content counts.
        self.assertIsNotNone(repo['latest_version_href'])

        self.assertIn(
            list(RPM_KICKSTART_FIXTURE_SUMMARY.items())[0],
            get_content_summary(repo).items(),
        )
        self.assertIn(
            list(RPM_KICKSTART_FIXTURE_SUMMARY.items())[0],
            get_added_content_summary(repo).items(),
        )

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        response = self.client.using_handler(api.json_handler).post(
            urljoin(repo["pulp_href"], "sync/"), data
        )
        sync_task = self.client.get(response["task"])
        created_at = self.parse_date_from_string(sync_task["pulp_created"])
        started_at = self.parse_date_from_string(sync_task["started_at"])
        finished_at = self.parse_date_from_string(sync_task["finished_at"])
        task_duration = finished_at - started_at
        waiting_time = started_at - created_at
        print("\n->  Re-sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(),
            service=task_duration.total_seconds()
        ))
        repo = self.client.get(repo['pulp_href'])

        # Check that nothing has changed since the last sync.
        self.assertNotEqual(latest_version_href, repo['latest_version_href'])
        self.assertIn(
            list(RPM_KICKSTART_FIXTURE_SUMMARY.items())[0],
            get_content_summary(repo).items(),
        )
        self.assertDictEqual(get_added_content_summary(repo), {})

    def test_centos7_on_demand(self):
        """Sync CentOS 7."""
        self.rpm_sync(url=CENTOS7_URL)

    def test_centos8_baseos_on_demand(self):
        """Sync CentOS 8 BaseOS."""
        self.rpm_sync(url=CENTOS8_BASEOS_URL)

    def test_centos8_appstream_on_demand(self):
        """Sync CentOS 8 AppStream."""
        self.rpm_sync(url=CENTOS8_APPSTREAM_URL)

    def test_centos8_kickstart_baseos_on_demand(self):
        """Kickstart Sync CentOS 8 BaseOS."""
        self.rpm_sync(url=CENTOS8_KICKSTART_BASEOS_URL)

    def test_centos8_kickstart_appstream_on_demand(self):
        """Kickstart Sync CentOS 8 AppStream."""
        self.rpm_sync(url=CENTOS8_KICKSTART_APP_URL)
