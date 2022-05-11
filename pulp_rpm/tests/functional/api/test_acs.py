from pulp_smash import config

from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    monitor_task_group,
    PulpTaskError,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_content_summary,
)

from pulp_rpm.tests.functional.constants import (
    PULP_FIXTURES_BASE_URL,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_KICKSTART_ONLY_META_FIXTURE_URL,
    RPM_ONLY_METADATA_REPO_URL,
)
from pulp_rpm.tests.functional.utils import gen_rpm_client, gen_rpm_remote

from pulpcore.client.pulp_rpm import (
    AcsRpmApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
)


class AlternateContentSourceSyncTestCase(PulpTestCase):
    """
    Test Alternate Content Source.

    1. Create ACS
    2. Sync from repo where only metadata is
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.acs_api = AcsRpmApi(cls.client)
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)

    @classmethod
    def tearDownClass(cls):
        """Tear down."""
        delete_orphans()

    def do_test(self, acs_url, paths, remote_url):
        """Sync with ACS test."""
        # ACS is rpm-unsigned repository which has all packages needed
        acs_remote = self.remote_api.create(gen_rpm_remote(url=acs_url, policy="on_demand"))
        self.addCleanup(self.remote_api.delete, acs_remote.pulp_href)

        acs_data = {
            "name": "alternatecontentsource",
            "remote": acs_remote.pulp_href,
            "paths": paths,
        }
        acs = self.acs_api.create(acs_data)
        self.addCleanup(self.acs_api.delete, acs.pulp_href)

        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        remote = self.remote_api.create(gen_rpm_remote(url=remote_url))
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # Sync repo with metadata only, before ACS refresh it should fail
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)

        with self.assertRaises(PulpTaskError) as ctx:
            sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
            monitor_task(sync_response.task)

        self.assertIn("404, message='Not Found'", ctx.exception.task.error["description"])

        # ACS refresh
        acs_refresh = self.acs_api.refresh(acs.pulp_href)
        monitor_task_group(acs_refresh.task_group)

        # Sync repository with metadata only
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        return self.repo_api.read(repo.pulp_href)

    def test_acs_simple(self):
        """Test to sync repo with use of ACS."""
        repo = self.do_test(
            acs_url=PULP_FIXTURES_BASE_URL,
            paths=["rpm-unsigned/"],
            remote_url=RPM_ONLY_METADATA_REPO_URL,
        )

        self.assertEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)

    def test_acs_with_dist_tree(self):
        """Test to sync repo with distribution tree."""
        repo = self.do_test(
            acs_url=PULP_FIXTURES_BASE_URL,
            paths=["rpm-distribution-tree/"],
            remote_url=RPM_KICKSTART_ONLY_META_FIXTURE_URL,
        )

        self.assertEqual(get_content_summary(repo.to_dict()), RPM_KICKSTART_FIXTURE_SUMMARY)
