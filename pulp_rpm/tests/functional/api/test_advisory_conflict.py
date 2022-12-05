"""Tests to test advisory conflict resolution functionality."""

from pulp_rpm.tests.functional.constants import (
    RPM_ADVISORY_DIFFERENT_PKGLIST_URL,
    RPM_ADVISORY_TEST_ID,
    RPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
)

from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulp_rpm import (
    ContentAdvisoriesApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)


class AdvisoryConflictTestCase(PulpTestCase):
    """Test advisory conflicts."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.advisory_api = ContentAdvisoriesApi(cls.client)
        delete_orphans()

        def _sync(url=None):
            repo = cls.repo_api.create(gen_repo())
            remote = cls.remote_api.create(gen_rpm_remote(url))
            repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
            sync_response = cls.repo_api.sync(repo.pulp_href, repository_sync_data)
            monitor_task(sync_response.task)
            return cls.repo_api.read(repo.pulp_href)

        # sync repos to get two conflicting advisories to use later in tests
        cls.repo_rpm_unsigned = _sync(url=RPM_UNSIGNED_FIXTURE_URL)
        cls.repo_rpm_advisory_diffpkgs = _sync(url=RPM_ADVISORY_DIFFERENT_PKGLIST_URL)
        cls.advisory_rpm_unsigned_href = (
            cls.advisory_api.list(
                repository_version=cls.repo_rpm_unsigned.latest_version_href,
                id=RPM_ADVISORY_TEST_ID,
            )
            .results[0]
            .pulp_href
        )
        cls.advisory_rpm_advisory_diffpkgs_href = (
            cls.advisory_api.list(
                repository_version=cls.repo_rpm_advisory_diffpkgs.latest_version_href,
                id=RPM_ADVISORY_TEST_ID,
            )
            .results[0]
            .pulp_href
        )

    @classmethod
    def tearDownClass(cls):
        """Clean up resources created in the setUp class."""
        cls.repo_api.delete(cls.repo_rpm_unsigned.pulp_href)
        cls.repo_api.delete(cls.repo_rpm_advisory_diffpkgs.pulp_href)

    def test_two_advisories_same_id_to_repo(self):
        """
        Test when two different advisories with the same id are added to a repo.

        Should merge the two advisories into a single one.
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        data = {
            "add_content_units": [
                self.advisory_rpm_unsigned_href,
                self.advisory_rpm_advisory_diffpkgs_href,
            ]
        }
        response = self.repo_api.modify(repo.pulp_href, data)
        monitor_task(response.task)
        a_repo = self.repo_api.read(repo.pulp_href)

        duplicated_advisory_list = self.advisory_api.list(
            repository_version=a_repo.latest_version_href,
            id=RPM_ADVISORY_TEST_ID,
        ).results
        self.assertEqual(1, len(duplicated_advisory_list))
