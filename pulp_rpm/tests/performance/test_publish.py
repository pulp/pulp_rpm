# coding=utf-8
"""Tests that publish rpm plugin repositories."""
import unittest
from datetime import datetime
from html.parser import HTMLParser
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

from productmd.treeinfo import TreeInfo

from pulp_smash import api, config, utils
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_added_content_summary,
    get_content,
    get_content_summary,
)

from pulp_rpm.tests.functional.constants import (
    RPM_DISTRIBUTION_PATH,
    RPM_KICKSTART_CONTENT_NAME,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_PUBLICATION_PATH,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    CENTOS6_URL,
    CENTOS7_URL,
    CENTOS8_APPSTREAM_URL,
    CENTOS8_BASEOS_URL,
    CENTOS8_KICKSTART_APP_URL,
    CENTOS8_KICKSTART_BASEOS_URL,
    EPEL7_URL,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class PackagesHtmlParser(HTMLParser):
    """HTML parser that looks for the first link to a file.

    This parser look for the first link that doesn't have a trailing slash. It then sets the
    package_href attribute to the value of the href.
    """

    package_href = None

    def handle_starttag(self, tag, attrs):
        """Looks for a tags that don't end with a slash."""
        if not self.package_href:
            if tag == "a" and not attrs[0][1].endswith("/"):
                self.package_href = attrs[0][1]
        else:
            super().handle_starttag(tag, attrs)


class PublishTestCase(unittest.TestCase):
    """Publish repositories with the rpm plugin."""

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

    def rpm_publish(self, url=RPM_KICKSTART_FIXTURE_URL, policy='on_demand'):
        """Publish repositories with the rpm plugin.

        This test targets the following issue:
        `Pulp #5630 <https://pulp.plan.io/issues/5630>`_.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Assert that distribution_tree units were added and are present in the repo.
        6. Publish
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
            RPM_PACKAGE_CONTENT_NAME,
            get_content_summary(repo).keys(),
        )
        self.assertIn(
            RPM_PACKAGE_CONTENT_NAME,
            get_added_content_summary(repo).keys(),
        )

        repo = self.client.get(repo['pulp_href'])

        # Publishing
        body = {"repository": repo["pulp_href"]}
        response = self.client.using_handler(api.json_handler).post(RPM_PUBLICATION_PATH, body)
        publish_task = self.client.get(response["task"])
        created_at = self.parse_date_from_string(publish_task["pulp_created"])
        started_at = self.parse_date_from_string(publish_task["started_at"])
        finished_at = self.parse_date_from_string(publish_task["finished_at"])
        task_duration = finished_at - started_at
        waiting_time = started_at - created_at
        print("\n->     Publish => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(),
            service=task_duration.total_seconds()
        ))
        return publish_task["created_resources"][0]

    def test_epel7(self):
        """Publish EPEL 7."""
        self.rpm_publish(url=EPEL7_URL)

    def test_centos6(self):
        """Publish CentOS 6."""
        self.rpm_publish(url=CENTOS6_URL)

    def test_centos7(self):
        """Publish CentOS 7."""
        self.rpm_publish(url=CENTOS7_URL)

    def test_centos8_baseos(self):
        """Publish CentOS 8 BaseOS."""
        publication_href = self.rpm_publish(url=CENTOS8_BASEOS_URL)
        # Test that the .treeinfo file is available and AppStream sub-repo is published correctly
        body = {"publication": publication_href,
                "name": "centos8",
                "base_path": "centos8"}
        response = self.client.using_handler(api.json_handler).post(RPM_DISTRIBUTION_PATH, body)
        distribution_task = self.client.get(response["task"])
        distribution_href = distribution_task["created_resources"][0]
        self.addCleanup(self.client.delete, distribution_href)
        distribution = self.client.get(distribution_href)
        treeinfo_file = utils.http_get(urljoin(distribution["base_url"], ".treeinfo"))
        treeinfo = TreeInfo()
        with NamedTemporaryFile('wb') as temp_file:
            temp_file.write(treeinfo_file)
            temp_file.flush()
            treeinfo.load(f=temp_file.name)
        for variant_name, variant in treeinfo.variants.variants.items():
            if variant_name == "BaseOS":
                self.assertEqual(variant.paths.repository, ".")
                self.assertEqual(variant.paths.packages, "Packages")
            elif variant_name == "AppStream":
                self.assertEqual(variant.paths.repository, "AppStream")
                self.assertEqual(variant.paths.packages, "AppStream/Packages")
                # Find the first package in the 'AppStream/Packages/a/' directory and download it
                parser = PackagesHtmlParser()
                a_packages_href = urljoin(distribution["base_url"],
                                          "{}/a/".format(variant.paths.packages))
                a_packages_listing = utils.http_get(a_packages_href)
                parser.feed(a_packages_listing.__str__())
                full_package_path = urljoin(a_packages_href, parser.package_href)
                utils.http_get(full_package_path)

    def test_centos8_appstream(self):
        """Publish CentOS 8 AppStream."""
        self.rpm_publish(url=CENTOS8_APPSTREAM_URL)

    def test_centos8_kickstart_baseos(self):
        """Kickstart Publish CentOS 8 BaseOS."""
        self.rpm_publish(url=CENTOS8_KICKSTART_BASEOS_URL)

    def test_centos8_kickstart_appstream(self):
        """Kickstart Publish CentOS 8 AppStream."""
        self.rpm_publish(url=CENTOS8_KICKSTART_APP_URL)
