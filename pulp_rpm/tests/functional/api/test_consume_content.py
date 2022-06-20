"""Verify whether package manager, yum/dnf, can consume content from Pulp."""
import unittest
import itertools

from pulpcore.client.pulpcore import ArtifactsApi, ApiClient as CoreApiClient
from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
)
from pulp_smash import api, cli, config, utils
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
    sync,
)

from pulp_rpm.tests.functional.utils import (
    gen_rpm_remote,
    gen_rpm_client,
    init_signed_repo_configuration,
)
from pulp_rpm.tests.functional.constants import (
    RPM_DISTRIBUTION_PATH,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    REPO_WITH_XML_BASE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_rpm.tests.functional.utils import publish

import requests


class PackageManagerConsumeTestCase(PulpTestCase):
    """Verify whether package manager can consume content from Pulp."""

    @classmethod
    def setUpClass(cls):
        """Verify whether dnf or yum are present."""
        cls.cfg = config.get_config()
        configuration = cls.cfg.get_bindings_config()
        core_client = CoreApiClient(configuration)
        cls.artifacts_api = ArtifactsApi(core_client)
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)
        cls.before_consumption_artifact_count = 0
        cls.pkg_mgr = cli.PackageManager(cls.cfg)
        cls.pkg_mgr.raise_if_unsupported(unittest.SkipTest, "This test requires dnf or yum.")

    def _has_dnf(self):
        return self.pkg_mgr.name == "dnf"

    def test_on_demand_policy_mirror_complete(self):
        """Verify that content synced with on_demand policy mode can be consumed."""
        delete_orphans()
        self.do_test("on_demand", sync_policy="mirror_complete")
        new_artifact_count = self.artifacts_api.list().count
        self.assertGreater(new_artifact_count, self.before_consumption_artifact_count)

    def test_streamed_policy_mirror_complete(self):
        """Verify that content synced with streamed policy mode can be consumed."""
        delete_orphans()
        self.do_test("streamed", sync_policy="mirror_complete")
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def test_immediate_policy_mirror_complete(self):
        """Verify that content synced with immediate policy mode can be consumed."""
        delete_orphans()
        self.do_test("immediate", sync_policy="mirror_complete")
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def test_on_demand_policy_mirror_content_only(self):
        """Verify that content synced with on_demand policy mode can be consumed."""
        delete_orphans()
        self.do_test("on_demand", sync_policy="mirror_content_only")
        new_artifact_count = self.artifacts_api.list().count
        self.assertGreater(new_artifact_count, self.before_consumption_artifact_count)

    def test_streamed_policy_mirror_content_only(self):
        """Verify that content synced with streamed policy mode can be consumed."""
        delete_orphans()
        self.do_test("streamed", sync_policy="mirror_content_only")
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def test_immediate_policy_mirror_content_only(self):
        """Verify that content synced with immediate policy mode can be consumed."""
        delete_orphans()
        self.do_test("immediate", sync_policy="mirror_content_only")
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def test_on_demand_policy_additive(self):
        """Verify that content synced with on_demand policy can be consumed."""
        delete_orphans()
        self.do_test("on_demand", sync_policy="additive")
        new_artifact_count = self.artifacts_api.list().count
        self.assertGreater(new_artifact_count, self.before_consumption_artifact_count)

    def test_streamed_policy_additive(self):
        """Verify that content synced with streamed policy can be consumed."""
        delete_orphans()
        self.do_test("streamed", sync_policy="additive")
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def test_immediate_policy_additive(self):
        """Verify that content synced with immediate policy can be consumed."""
        delete_orphans()
        self.do_test("immediate", sync_policy="additive")
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def test_with_xml_base_in_metadata(self):
        """Verify the package manager can consume content synced from a repo that uses xml:base.

        xml:base / location_base is a "feature" of RPM metadata that tells the client to use a
        completely different base path when looking up relative paths.
        """
        delete_orphans()
        self.do_test("immediate", sync_policy="mirror_content_only", url=REPO_WITH_XML_BASE_URL)
        new_artifact_count = self.artifacts_api.list().count
        self.assertEqual(new_artifact_count, self.before_consumption_artifact_count)

    def do_test(self, policy, sync_policy, url=RPM_UNSIGNED_FIXTURE_URL):
        """Verify whether package manager can consume content from Pulp."""
        if not self._has_dnf():
            self.skipTest("This test requires dnf")

        body = gen_rpm_remote(policy=policy)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repo = self.repo_api.create(gen_repo(autopublish=sync_policy != "mirror_complete"))
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        before_sync_artifact_count = self.artifacts_api.list().count
        self.assertEqual(before_sync_artifact_count, 0)

        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href, sync_policy=sync_policy
        )
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        created_resources = monitor_task(sync_response.task).created_resources

        publication_href = [r for r in created_resources if "publication" in r][0]
        self.addCleanup(self.publications.delete, publication_href)

        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = self.distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.distributions.read(created_resources[0])
        self.addCleanup(self.distributions.delete, distribution.pulp_href)

        cli_client = cli.Client(self.cfg)
        cli_client.run(("sudo", "dnf", "config-manager", "--add-repo", distribution.base_url))
        repo_id = "*{}_".format(distribution.base_path)
        cli_client.run(
            (
                "sudo",
                "dnf",
                "config-manager",
                "--save",
                "--setopt={}.gpgcheck=0".format(repo_id),
                repo_id,
            )
        )
        self.addCleanup(cli_client.run, ("sudo", "dnf", "config-manager", "--disable", repo_id))
        self.before_consumption_artifact_count = self.artifacts_api.list().count
        rpm_name = "walrus"
        self.pkg_mgr.install(rpm_name)
        self.addCleanup(self.pkg_mgr.uninstall, rpm_name)
        rpm = cli_client.run(("rpm", "-q", rpm_name)).stdout.strip().split("-")
        self.assertEqual(rpm_name, rpm[0])


class ConsumeSignedRepomdTestCase(PulpTestCase):
    """A test case that verifies the publishing of a signed repository."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.cli_client = cli.Client(cls.cfg)
        cls.pkg_mgr = cli.PackageManager(cls.cfg)
        cls.api_client = api.Client(cls.cfg, api.json_handler)

        api_root = utils.get_pulp_setting(cls.cli_client, "API_ROOT").lstrip("/")

        signing_services = cls.api_client.using_handler(api.page_handler).get(
            f"{api_root}api/v3/signing-services/", params={"name": "sign-metadata"}
        )
        # NOTE: This is not used by the CI, only by local tests. The CI uses a separate
        # environment for API tests and Pulp, so the API tests don't have direct access
        # to run terminal commands. And cli.Client has issues with it as well.
        #
        # In the event of issues go look at post_before_script.sh.
        if not signing_services:
            init_signed_repo_configuration()

            signing_services = cls.api_client.using_handler(api.page_handler).get(
                f"{api_root}api/v3/signing-services/", params={"name": "sign-metadata"}
            )

        cls.metadata_signing_service = signing_services[0]

    def _has_dnf(self):
        return self.pkg_mgr.name == "dnf"

    def test_publish_signed_repo_metadata(self):
        """Test if a package manager is able to install packages from a signed repository."""
        distribution = self.create_distribution()
        self.init_repository_config(distribution)
        self.install_package()

    def test_config_dot_repo(self):
        """Test all possible combinations of gpgcheck options made to a publication."""
        test_options = {
            "gpgcheck": [0, 1],
            "repo_gpgcheck": [0, 1],
            "has_signing_service": [True, False],
        }
        cartesian_product = itertools.product(*test_options.values())
        func_params = [dict(zip(test_options.keys(), a)) for a in cartesian_product]

        for params in func_params:
            self.check_config_dot_repo_options(**params)

    def check_config_dot_repo_options(self, gpgcheck=0, repo_gpgcheck=0, has_signing_service=True):
        """Test if the generated config.repo has the right content."""
        distribution = self.create_distribution(
            gpgcheck=gpgcheck, repo_gpgcheck=repo_gpgcheck, has_signing_service=has_signing_service
        )
        response = requests.get(f'{distribution["base_url"]}/config.repo')

        options = f"gpgcheck={gpgcheck}, repo_gpgcheck={repo_gpgcheck}, ss={has_signing_service}"

        self.assertEqual(response.status_code, 200, options)
        self.assertIn(bytes(f'[{distribution["name"]}]\n', "utf-8"), response.content, options)
        self.assertIn(
            bytes(f'baseurl={distribution["base_url"]}\n', "utf-8"), response.content, options
        )
        self.assertIn(bytes(f"gpgcheck={gpgcheck}\n", "utf-8"), response.content, options)
        self.assertIn(bytes(f"repo_gpgcheck={repo_gpgcheck}\n", "utf-8"), response.content, options)

        if has_signing_service:
            self.assertIn(
                bytes(f'gpgkey={distribution["base_url"]}repodata/repomd.xml.key', "utf-8"),
                response.content,
                options,
            )

    def create_distribution(self, gpgcheck=0, repo_gpgcheck=0, has_signing_service=True):
        """Create a distribution with a repository that contains a signing service."""
        repo_params = {}
        if has_signing_service:
            repo_params["metadata_signing_service"] = self.metadata_signing_service["pulp_href"]

        repo = self.api_client.post(RPM_REPO_PATH, gen_repo(**repo_params))

        self.addCleanup(self.api_client.delete, repo["pulp_href"])

        remote = self.api_client.post(RPM_REMOTE_PATH, gen_rpm_remote())
        self.addCleanup(self.api_client.delete, remote["pulp_href"])

        sync(self.cfg, remote, repo)
        repo = self.api_client.get(repo["pulp_href"])

        self.assertIsNotNone(repo["latest_version_href"])

        publication = publish(self.cfg, repo, gpgcheck=gpgcheck, repo_gpgcheck=repo_gpgcheck)
        self.addCleanup(self.api_client.delete, publication["pulp_href"])

        body = gen_distribution()
        body["publication"] = publication["pulp_href"]
        distribution = self.api_client.using_handler(api.task_handler).post(
            RPM_DISTRIBUTION_PATH, body
        )
        self.addCleanup(self.api_client.delete, distribution["pulp_href"])

        return distribution

    def init_repository_config(self, distribution):
        """
        Create and initialize the repository's configuration.

        This configuration is going to be used by the package manager (dnf) afterwards.
        """
        if not self._has_dnf():
            self.skipTest("This test requires dnf")

        self.cli_client.run(
            ("sudo", "dnf", "config-manager", "--add-repo", distribution["base_url"])
        )
        repo_id = "*{}_".format(distribution["base_path"])
        public_key_url = f"{distribution['base_url']}repodata/repomd.xml.key"
        self.cli_client.run(
            (
                "sudo",
                "dnf",
                "config-manager",
                "--save",
                f"--setopt={repo_id}.gpgcheck=0",
                f"--setopt={repo_id}.repo_gpgcheck=1",
                f"--setopt={repo_id}.gpgkey={public_key_url}",
                repo_id,
            )
        )
        self.addCleanup(
            self.cli_client.run, ("sudo", "dnf", "config-manager", "--disable", repo_id)
        )

    def install_package(self):
        """Install and verify the installed package."""
        rpm_name = "walrus"
        self.pkg_mgr.install(rpm_name)
        self.addCleanup(self.pkg_mgr.uninstall, rpm_name)
        rpm = self.cli_client.run(("rpm", "-q", rpm_name)).stdout.strip().split("-")
        self.assertEqual(rpm_name, rpm[0])
