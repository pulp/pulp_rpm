import requests

from pulp_smash import config
from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_distribution,
    gen_repo,
)

from pulp_rpm.tests.functional.utils import gen_rpm_client

from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    RepositoriesRpmApi,
    PublicationsRpmApi,
    RpmRpmPublication,
)


class ContentHandlerTests(PulpTestCase):
    """Whether the RpmDistribution.content_handler* methods work."""

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up after testing."""
        delete_orphans(cls.cfg)

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.publications_api = PublicationsRpmApi(cls.client)
        cls.distributions_api = DistributionsRpmApi(cls.client)
        delete_orphans(cls.cfg)

    def setUp(self) -> None:
        """Set up the test."""
        self._setUp()

    def _setUp(self, cleanup=True):
        """Helper to the setUp method."""
        self.repo = self.repo_api.create(gen_repo())

        publish_data = RpmRpmPublication(repository=self.repo.pulp_href)
        publish_response = self.publications_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        dist_data = gen_distribution(publication=publication_href)
        dist_response = self.distributions_api.create(dist_data)
        created_resources = monitor_task(dist_response.task).created_resources
        self.dist = self.distributions_api.read(created_resources[0])
        if cleanup:
            self.addCleanup(self.repo_api.delete, self.repo.pulp_href)
            self.addCleanup(self.publications_api.delete, publication_href)
            self.addCleanup(self.distributions_api.delete, self.dist.pulp_href)

    def testConfigRepoInListingUnsigned(self):
        """Whether the served resources are in the directory listing."""
        resp = requests.get(self.dist.base_url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"config.repo", resp.content)
        self.assertNotIn(b"repomd.xml.key", resp.content)

    def testConfigRepoUnsigned(self):
        """Whether config.repo can be downloaded and has the right content."""
        self.config_repo_check()

    def testConfigRepoAutoDistribute(self):
        """Whether config.repo is properly served using auto-distribute."""
        self._setUp(cleanup=False)
        self.addCleanup(self.repo_api.delete, self.repo.pulp_href)
        self.addCleanup(self.distributions_api.delete, self.dist.pulp_href)
        publication_href = self.dist.publication
        body = {"repository": self.repo.pulp_href}
        monitor_task(self.distributions_api.partial_update(self.dist.pulp_href, body).task)
        # Check that distribution is now using repository to auto-distribute
        self.dist = self.distributions_api.read(self.dist.pulp_href)
        self.assertEqual(self.repo.pulp_href, self.dist.repository)
        self.assertIsNone(self.dist.publication)
        self.config_repo_check()
        # Delete publication and check that 404 is now returned
        self.publications_api.delete(publication_href)
        resp = requests.get(f"{self.dist.base_url}config.repo")
        self.assertEqual(resp.status_code, 404)

    def config_repo_check(self):
        """Helper to do the tests on config.repo."""
        resp = requests.get(f"{self.dist.base_url}config.repo")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(bytes(f"[{self.dist.name}]\n", "utf-8"), resp.content)
        self.assertIn(bytes(f"baseurl={self.dist.base_url}\n", "utf-8"), resp.content)
        self.assertIn(bytes("gpgcheck=0\n", "utf-8"), resp.content)
        self.assertIn(bytes("repo_gpgcheck=0", "utf-8"), resp.content)
