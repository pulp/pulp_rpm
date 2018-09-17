# coding=utf-8
"""Tests that publish rpm plugin repositories."""
import unittest
from random import choice
from urllib.parse import urljoin

from requests.exceptions import HTTPError

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_versions,
    publish,
    sync,
)

from pulp_rpm.tests.functional.utils import (
    gen_rpm_publisher,
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_PUBLISHER_PATH,
    RPM_REMOTE_PATH,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class PublishAnyRepoVersionTestCase(unittest.TestCase):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/PulpQE/pulp-smash/issues/897>`_
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
        client = api.Client(cfg, api.json_handler)

        body = gen_rpm_remote()
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        sync(cfg, remote, repo)

        publisher = client.post(RPM_PUBLISHER_PATH, gen_rpm_publisher())
        self.addCleanup(client.delete, publisher['_href'])

        # Step 1
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        for rpm_content in client.get(RPM_CONTENT_PATH)['results']:
            client.post(
                repo['_versions_href'],
                {'add_content_units': [rpm_content['_href']]}
            )
        version_hrefs = tuple(ver['_href'] for ver in get_versions(repo))
        non_latest = choice(version_hrefs[:-1])

        # Step 2
        publication = publish(cfg, publisher, repo)

        # Step 3
        self.assertEqual(publication['repository_version'], version_hrefs[-1])

        # Step 4
        publication = publish(cfg, publisher, repo, non_latest)

        # Step 5
        self.assertEqual(publication['repository_version'], non_latest)

        # Step 6
        with self.assertRaises(HTTPError):
            body = {
                'repository': repo['_href'],
                'repository_version': non_latest
            }
            client.post(urljoin(publisher['_href'], 'publish/'), body)
