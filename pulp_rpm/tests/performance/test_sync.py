# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import os
import unittest
from datetime import datetime
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_added_content_summary,
    get_content,
    get_content_summary,
)

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_REPOMETADATA,
    RPM_CDN_APPSTREAM_URL,
    RPM_CDN_BASEOS_URL,
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
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    skip_if
)
from pulpcore.client.pulp_rpm import (
    ContentRepoMetadataFilesApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL
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
        self.assertEqual(repo["latest_version_href"], f"{repo['pulp_href']}versions/0/")
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
        self.assertEqual(latest_version_href, repo['latest_version_href'])

    def test_centos7_on_demand(self):
        """Sync CentOS 7."""
        self.rpm_sync(url=CENTOS7_URL)

    def test_centos7_immediate(self):
        """Sync CentOS 7 with the immediate policy."""
        self.rpm_sync(url=CENTOS7_URL, policy='immediate')

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


class CDNTestCase(unittest.TestCase):
    """Sync a repository from CDN."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.repometadatafiles = ContentRepoMetadataFilesApi(cls.client)
        delete_orphans(cls.cfg)
        # Certificates processing
        cls.cdn_client_cert = False
        if os.environ['CDN_CLIENT_CERT'] \
                and os.environ['CDN_CLIENT_KEY'] \
                and os.environ['CDN_CA_CERT']:
            # strings have escaped newlines from environmental variable
            cls.cdn_client_cert = os.environ['CDN_CLIENT_CERT'].replace('\\n', '\n')
            cls.cdn_client_key = os.environ['CDN_CLIENT_KEY'].replace('\\n', '\n')
            cls.cdn_ca_cert = os.environ['CDN_CA_CERT'].replace('\\n', '\n')

    @skip_if(bool, "cdn_client_cert", False)
    def test_sync_with_certificate(self):
        """Test sync against CDN.

        1. create repository, appstream remote and sync
            - remote using certificates and tls validation
        2. create repository, baseos remote and sync
            - remote using certificates without tls validation
        3. Check both repositories were synced and both have its own 'productid' content
            - this test covering checking same repo metadata files with different relative paths
        """
        # 1. create repo, remote and sync them
        repo_appstream = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo_appstream.pulp_href)

        body = gen_rpm_remote(
            url=RPM_CDN_APPSTREAM_URL,
            client_cert=self.cdn_client_cert,
            client_key=self.cdn_client_key,
            ca_cert=self.cdn_ca_cert,
            policy="on_demand"
        )
        appstream_remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, appstream_remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=appstream_remote.pulp_href)
        sync_response = self.repo_api.sync(repo_appstream.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 2. create remote and re-sync
        repo_baseos = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo_baseos.pulp_href)

        body = gen_rpm_remote(
            url=RPM_CDN_BASEOS_URL, tls_validation=False,
            client_cert=self.cdn_client_cert,
            client_key=self.cdn_client_key,
            policy="on_demand"
        )
        baseos_remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, baseos_remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=baseos_remote.pulp_href)
        sync_response = self.repo_api.sync(repo_baseos.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # Get all 'productid' repo metadata files
        productids = [productid for productid in self.repometadatafiles.list().results if
                      productid.data_type == 'productid']

        # Update repositories info
        repo_baseos_dict = self.repo_api.read(repo_baseos.pulp_href).to_dict()
        repo_appstream_dict = self.repo_api.read(repo_appstream.pulp_href).to_dict()

        # Assert there are two productid content units and they have same checksum
        self.assertEqual(
            len(productids), 2
        )
        self.assertEqual(
            productids[0].checksum, productids[1].checksum
        )
        # Assert each repository has latest version 1 (it was synced)
        self.assertEqual(
            repo_appstream_dict['latest_version_href'].rstrip('/')[-1],
            '1'
        )
        self.assertEqual(
            repo_baseos_dict['latest_version_href'].rstrip('/')[-1],
            '1'
        )
        # Assert each repository has its own productid file
        self.assertEqual(
            get_content_summary(repo_appstream_dict)[PULP_TYPE_REPOMETADATA],
            1
        )
        self.assertEqual(
            get_content_summary(repo_baseos_dict)[PULP_TYPE_REPOMETADATA],
            1
        )
        self.assertNotEqual(
            get_content(repo_appstream_dict)[PULP_TYPE_REPOMETADATA][0]['relative_path'],
            get_content(repo_baseos_dict)[PULP_TYPE_REPOMETADATA][0]['relative_path']
        )
