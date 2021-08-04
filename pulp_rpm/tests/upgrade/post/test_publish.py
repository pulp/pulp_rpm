"""Tests that publish rpm plugin repositories."""
from random import choice


from pulp_smash import config
from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_content,
    gen_distribution,
    get_versions,
    modify_repo,
)

from pulp_rpm.tests.functional.constants import RPM_PACKAGE_CONTENT_NAME
from pulp_rpm.tests.functional.utils import gen_rpm_client, gen_rpm_remote
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    PublicationsRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
    RpmRpmPublication,
)
from pulpcore.client.pulp_rpm.exceptions import ApiException


class PublishAnyRepoVersionTestCase(PulpTestCase):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/pulp/pulp-smash/issues/897>`_
    """

    def test_all(self):
        """Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.
        """
        cfg = config.get_config()
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)
        publications = PublicationsRpmApi(client)
        distributions = DistributionsRpmApi(client)

        dist_path = "/pulp/content/pulp_pre_upgrade_test"
        url = cfg.get_content_host_base_url() + dist_path
        body = gen_rpm_remote(url=url)
        remote = remote_api.create(body)

        repo = repo_api.create(gen_repo())

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # Step 1
        repo = repo_api.read(repo.pulp_href)
        repo_content = get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]
        for rpm_content in repo_content:
            modify_repo(cfg, repo.to_dict(), remove_units=[rpm_content])
        version_hrefs = tuple(ver["pulp_href"] for ver in get_versions(repo.to_dict()))
        non_latest = choice(version_hrefs[1:-1])

        # Step 2
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        publication = publications.read(publication_href)

        # Step 3
        self.assertEqual(publication.repository_version, version_hrefs[-1])

        # Step 4
        publish_data.repository_version = non_latest
        publish_data.repository = None
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        publication = publications.read(publication_href)

        # Step 5
        body = gen_distribution()
        body["base_path"] = "pulp_post_upgrade_test"
        body["publication"] = publication.pulp_href

        distribution_response = distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = distributions.read(created_resources[0])

        # Step 6
        self.assertEqual(publication.repository_version, non_latest)

        # Step 7
        with self.assertRaises(ApiException):
            body = {"repository": repo.pulp_href, "repository_version": non_latest}
            publications.create(body)

        # Step 8
        url = cfg.get_content_host_base_url() + "/pulp/content/pulp_post_upgrade_test/"
        self.assertEqual(url, distribution.base_url, url)
