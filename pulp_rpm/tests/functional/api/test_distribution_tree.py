"""Tests distribution trees."""

from pulp_smash import config
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_rpm.tests.functional.utils import rpm_copy
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_content,
)

from pulp_rpm.tests.functional.utils import gen_rpm_client, gen_rpm_remote

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_DISTRIBUTION_TREE,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_DISTRIBUTION_TREE_CHANGED_ADDON_URL,
    RPM_DISTRIBUTION_TREE_CHANGED_MAIN_URL,
    RPM_DISTRIBUTION_TREE_CHANGED_VARIANT_URL,
)

from pulpcore.client.pulp_rpm import (
    ContentDistributionTreesApi,
    ContentPackagesApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)


class DistributionTreeCopyTestCase(PulpTestCase):
    """Test copy of distribution tree."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.dist_tree_api = ContentDistributionTreesApi(cls.client)
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        delete_orphans()

    def do_sync(self, remote_url):
        """Create and sync repository with remote_url.

        Returns (dict): created repository url
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=remote_url)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        return self.repo_api.read(repo.pulp_href).to_dict()

    def test_simple_copy_distribution_tree(self):
        """Sync repository with a distribution tree."""
        source_repo = self.do_sync(RPM_KICKSTART_FIXTURE_URL)
        dest_repo = self.repo_api.create(gen_repo()).to_dict()
        self.addCleanup(self.repo_api.delete, dest_repo["pulp_href"])

        config = [
            {
                "source_repo_version": source_repo["latest_version_href"],
                "dest_repo": dest_repo["pulp_href"],
            }
        ]

        rpm_copy(self.cfg, config, recursive=True)
        dest_repo = self.repo_api.read(dest_repo["pulp_href"]).to_dict()

        self.assertEqual(get_added_content_summary(dest_repo)[PULP_TYPE_DISTRIBUTION_TREE], 1)

    def test_dist_tree_copy_as_content(self):
        """Test sync distribution tree repository and copy it."""
        repo = self.do_sync(RPM_KICKSTART_FIXTURE_URL)
        repo_copy = self.repo_api.create(gen_repo()).to_dict()
        self.addCleanup(self.repo_api.delete, repo_copy["pulp_href"])
        distribution_tree_href = get_content(repo)[PULP_TYPE_DISTRIBUTION_TREE][0]["pulp_href"]

        copy_config = [
            {
                "source_repo_version": repo["latest_version_href"],
                "dest_repo": repo_copy["pulp_href"],
                "content": [distribution_tree_href],
            }
        ]
        rpm_copy(self.cfg, copy_config, recursive=True)

        repo_copy = self.repo_api.read(repo_copy["pulp_href"]).to_dict()

        self.assertEqual(
            get_content(repo)[PULP_TYPE_DISTRIBUTION_TREE],
            get_content(repo_copy)[PULP_TYPE_DISTRIBUTION_TREE],
        )
        self.assertEqual(repo["latest_version_href"].rstrip("/")[-1], "1")
        self.assertEqual(repo_copy["latest_version_href"].rstrip("/")[-1], "1")
        self.assertEqual(len(get_content(repo)[PULP_TYPE_DISTRIBUTION_TREE]), 1)
        self.assertEqual(len(get_content(repo_copy)[PULP_TYPE_DISTRIBUTION_TREE]), 1)


class DistributionTreeTest(PulpTestCase):
    """Test Distribution Trees."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()
        cls.dist_tree_api = ContentDistributionTreesApi(cls.client)
        cls.packages_api = ContentPackagesApi(cls.client)
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        delete_orphans()

    def do_test(self, repository=None, remote=None):
        """Sync a repository.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
        Returns (tuple):
            tuple of instances of
            pulp_rpm.app.models.repository.RpmRepository, pulp_rpm.app.models.repository.RpmRemote
        """
        if repository:
            repo = self.repo_api.read(repository.pulp_href)
        else:
            repo = self.repo_api.create(gen_repo())
            self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")

        if not remote:
            body = gen_rpm_remote()
            remote = self.remote_api.create(body)
        else:
            remote = self.remote_api.read(remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        return self.repo_api.read(repo.pulp_href), self.remote_api.read(remote.pulp_href)

    def test_sync_dist_tree_change_addon_repo(self):
        """Test changed addon repository."""
        addon_test_pkg_name = "test-srpm02"
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync & update repo object
        repo, remote = self.do_test(remote=remote)
        repo = self.repo_api.read(repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # check testing package is not present
        self.assertNotIn(
            addon_test_pkg_name,
            [pkg["name"] for pkg in self.packages_api.list().to_dict()["results"]],
        )

        # new remote
        body = gen_rpm_remote(RPM_DISTRIBUTION_TREE_CHANGED_ADDON_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # re-sync & update repo object
        repo, remote = self.do_test(repo, remote)
        repo = self.repo_api.read(repo.pulp_href)

        # check new pacakge is synced to subrepo
        self.assertIn(
            addon_test_pkg_name,
            [pkg["name"] for pkg in self.packages_api.list().to_dict()["results"]],
        )

    def test_sync_dist_tree_change_main_repo(self):
        """Test changed main repository."""
        main_repo_test_pkg_name = "test-srpm01"
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync & update repo object
        repo, remote = self.do_test(remote=remote)
        repo = self.repo_api.read(repo.pulp_href)
        repo_version = repo.latest_version_href.rstrip("/")[-1]
        self.addCleanup(self.remote_api.delete, remote.pulp_href)
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # new remote
        body = gen_rpm_remote(RPM_DISTRIBUTION_TREE_CHANGED_MAIN_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # re-sync & update repo object
        repo, remote = self.do_test(repo, remote)
        repo = self.repo_api.read(repo.pulp_href)
        updated_repo_version = repo.latest_version_href.rstrip("/")[-1]

        # Assert new content was added and repo version was increased
        self.assertNotEqual(repo_version, updated_repo_version)
        self.assertIn(
            main_repo_test_pkg_name,
            [pkg["name"] for pkg in self.packages_api.list().to_dict()["results"]],
        )

    def test_sync_dist_tree_change_variant_repo(self):
        """Test changed variant repository."""
        variant_test_pkg_name = "test-srpm03"
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL)
        remote = self.remote_api.create(body)

        # sync & update repo object
        repo, remote = self.do_test(remote=remote)
        repo = self.repo_api.read(repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # check testing package is not present
        self.assertNotIn(
            variant_test_pkg_name,
            [pkg["name"] for pkg in self.packages_api.list().to_dict()["results"]],
        )

        # new remote
        body = gen_rpm_remote(RPM_DISTRIBUTION_TREE_CHANGED_VARIANT_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # re-sync & update repo object
        repo, remote = self.do_test(repo, remote)
        repo = self.repo_api.read(repo.pulp_href)

        # check new pacakge is synced to subrepo
        self.assertIn(
            variant_test_pkg_name,
            [pkg["name"] for pkg in self.packages_api.list().to_dict()["results"]],
        )

    def test_remove_repo_with_distribution_tree(self):
        """Sync repository with distribution tree and remove the repository."""
        body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)
        num_repos_start = self.repo_api.list().count
        num_disttrees_start = self.dist_tree_api.list().count

        repo, _ = self.do_test(remote=remote)
        task = self.repo_api.delete(repo.pulp_href)
        monitor_task(task.task)

        self.assertEqual(self.repo_api.list().count, num_repos_start)
        # Remove orphans and check if distribution tree was removed.
        delete_orphans()
        self.assertEqual(self.dist_tree_api.list().count, num_disttrees_start)
