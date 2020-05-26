# coding=utf-8
"""Tests that sync rpm plugin repositories."""
import unittest

from random import choice
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
    PULP_TYPE_PACKAGE,
    RPM_KICKSTART_CONTENT_NAME,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    RPM_UNSIGNED_FIXTURE_URL,
    UPDATERECORD_CONTENT_PATH,
    RPM_CONTENT_PATH,
)
from pulp_rpm.tests.functional.utils import gen_rpm_client, gen_rpm_remote, monitor_task, rpm_copy
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    ContentPackagesApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)


class BaseCopy(unittest.TestCase):
    """Base-class for shared code for copy-test-subclasses."""

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


class BasicCopyTestCase(BaseCopy):
    """Copy units between repositories with the rpm plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        delete_orphans(cls.cfg)

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


class DependencySolvingTestCase(BaseCopy):
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
        1. start with standard repo-setup
        2. Use the RPM copy API to units from the repo to the empty repo.
        3. Assert that the correct number of units were added and are present in the dest repo.
        """
        source_repo, dest_repo = self._setup_repos()
        rpm_copy(self.cfg, source_repo, dest_repo, criteria, recursive=True)
        dest_repo = self.client.get(dest_repo['pulp_href'])

        # Check that we have the correct content counts.
        self.assertDictEqual(get_content_summary(dest_repo), expected_results)
        self.assertDictEqual(
            get_added_content_summary(dest_repo), expected_results,
        )

    def test_all_content_recursive(self):
        """Test requesting all-rpm-uipdate-content/recursive (see #6519)."""
        source_repo, dest_repo = self._setup_repos()
        latest_href = source_repo["latest_version_href"]

        advisory_content = \
            self.client.get(f"{UPDATERECORD_CONTENT_PATH}?repository_version={latest_href}")
        advisories_to_copy = \
            [rslt["pulp_href"] for rslt in advisory_content["results"]]
        rpm_content = self.client.get(f"{RPM_CONTENT_PATH}?repository_version={latest_href}")
        rpms_to_copy = [rslt["pulp_href"] for rslt in rpm_content["results"]]
        content_to_copy = set()
        content_to_copy.update(advisories_to_copy)
        content_to_copy.update(rpms_to_copy)
        config = [{
            'source_repo_version': latest_href,
            'dest_repo': dest_repo['pulp_href'],
            'content': list(content_to_copy)
        }]

        rpm_copy(self.cfg, config, recursive=True)

        dest_repo = self.client.get(dest_repo['pulp_href'])
        latest_href = dest_repo["latest_version_href"]

        # check advisories copied
        dc = self.client.get(f"{UPDATERECORD_CONTENT_PATH}?repository_version={latest_href}")
        dest_content = [c["pulp_href"] for c in dc["results"]]
        self.assertEqual(sorted(advisories_to_copy), sorted(dest_content))

        # check rpms copied
        dc = self.client.get(f"{RPM_CONTENT_PATH}?repository_version={latest_href}")
        dest_content = [c["pulp_href"] for c in dc["results"]]
        self.assertEqual(sorted(rpms_to_copy), sorted(dest_content))


class StrictPackageCopyTestCase(unittest.TestCase):
    """Test strict copy of package and its dependencies."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.rpm_content_api = ContentPackagesApi(cls.client)
        cls.test_package = 'whale'
        cls.test_package_dependencies = ['shark', 'stork']
        delete_orphans(cls.cfg)

    def test_strict_copy_package_to_empty_repo(self):
        """Test copy package and its dependencies to empty repository.

        - Create repository and populate it
        - Create empty repository
        - Use 'copy' to copy 'whale' package with dependencies
        - assert package and its dependencies were copied
        """
        empty_repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, empty_repo.pulp_href)

        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        repo = self.repo_api.read(repo.pulp_href)
        test_package_href = [
            pkg
            for pkg in get_content(repo.to_dict())[PULP_TYPE_PACKAGE]
            if pkg['name'] == self.test_package
        ][0]['pulp_href']
        package_to_copy = []
        package_to_copy.append(test_package_href)

        config = [{
            'source_repo_version': repo.latest_version_href,
            'dest_repo': empty_repo.pulp_href,
            'content': package_to_copy
        }]

        rpm_copy(self.cfg, config, recursive=True)
        empty_repo = self.repo_api.read(empty_repo.pulp_href)
        empty_repo_packages = [
            pkg['name']
            for pkg in get_content(empty_repo.to_dict())[PULP_TYPE_PACKAGE]
        ]

        # assert that only 3 packages are copied (original package with its two dependencies)
        self.assertEqual(len(empty_repo_packages), 3)
        # assert dependencies package names
        for dependency in self.test_package_dependencies:
            self.assertIn(dependency, empty_repo_packages)

    def test_strict_copy_package_to_existing_repo(self):
        """Test copy package and its dependencies to empty repository.

        - Create repository and populate it
        - Create second repository with package fullfiling test package dependency
        - Use 'copy' to copy 'whale' package with dependencies
        - assert package and its missing dependencies were copied
        """
        # prepare final_repo - copy to repository
        final_repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, final_repo.pulp_href)

        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(final_repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        final_repo = self.repo_api.read(final_repo.pulp_href)

        # prepare repository - copy from repository
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        repo = self.repo_api.read(repo.pulp_href)

        # remove test package and one dependency package from final repository
        dependency_to_remove = choice(self.test_package_dependencies)
        data = {
            "remove_content_units": [
                pkg.pulp_href
                for pkg in self.rpm_content_api.list().results
                if pkg.name in (dependency_to_remove, self.test_package)
            ]
        }
        response = self.repo_api.modify(final_repo.pulp_href, data)
        monitor_task(response.task)
        final_repo = self.repo_api.read(final_repo.pulp_href)

        # get package to copy
        test_package_href = [
            pkg
            for pkg in get_content(repo.to_dict())[PULP_TYPE_PACKAGE]
            if pkg['name'] == self.test_package
        ][0]['pulp_href']
        package_to_copy = []
        package_to_copy.append(test_package_href)

        config = [{
            'source_repo_version': repo.latest_version_href,
            'dest_repo': final_repo.pulp_href,
            'content': package_to_copy
        }]

        copy_response = rpm_copy(self.cfg, config, recursive=True)

        # check only two packages was copied, original package to copy and only one
        # of its dependency as one is already present
        self.assertEqual(
            copy_response['content_summary']['added'][PULP_TYPE_PACKAGE]['count'], 2
        )
