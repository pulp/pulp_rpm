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
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = self.publications_api.create(publish_data)
        created_resources = monitor_task(publish_response.task)
        publication_href = created_resources[0]
        self.addCleanup(self.publications_api.delete, publication_href)

        dist_data = gen_distribution(publication=publication_href)
        dist_response = self.distributions_api.create(dist_data)
        created_resources = monitor_task(dist_response.task)
        self.dist = self.distributions_api.read(created_resources[0])
        self.addCleanup(self.distributions_api.delete, self.dist.pulp_href)

    def testConfigRepoInListingUnsigned(self):
        """Whether the served resources are in the directory listing."""
        resp = requests.get(self.dist.base_url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'config.repo', resp.content)
        self.assertNotIn(b'public.key', resp.content)

    def testConfigRepoUnsigned(self):
        """Whether config.repo can be downloaded and has the right content."""
        resp = requests.get(f'{self.dist.base_url}config.repo')

        self.assertEqual(resp.status_code, 200)
        self.assertIn(bytes(f'[{self.dist.name}]\n', 'utf-8'), resp.content)
        self.assertIn(bytes(f'baseurl={self.dist.base_url}\n', 'utf-8'), resp.content)
        self.assertIn(bytes('gpgcheck=0\n', 'utf-8'), resp.content)
        self.assertIn(bytes('repo_gpgcheck=0', 'utf-8'), resp.content)
