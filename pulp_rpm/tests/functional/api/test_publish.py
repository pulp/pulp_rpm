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
    get_content,
    get_content_summary,
    get_versions,
    publish,
    sync,
)

from pulp_rpm.tests.functional.utils import (
    gen_rpm_publisher,
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.constants import (
    DRPM_UNSIGNED_FIXTURE_URL,
    RPM_ALT_LAYOUT_FIXTURE_URL,
    RPM_FIXTURE_SUMMARY,
    RPM_LONG_UPDATEINFO_FIXTURE_URL,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_PUBLISHER_PATH,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_REMOTE_PATH,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
    SRPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class PublishAnyRepoVersionTestCase(unittest.TestCase):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/PulpQE/pulp-smash/issues/897>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest
           ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.
        """
        body = gen_rpm_remote()
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        sync(self.cfg, remote, repo)

        publisher = self.client.post(RPM_PUBLISHER_PATH, gen_rpm_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])

        # Step 1
        repo = self.client.get(repo['_href'])
        for rpm_content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]:
            self.client.post(
                repo['_versions_href'],
                {'add_content_units': [rpm_content['_href']]}
            )
        version_hrefs = tuple(ver['_href'] for ver in get_versions(repo))
        non_latest = choice(version_hrefs[:-1])

        # Step 2
        publication = publish(self.cfg, publisher, repo)

        # Step 3
        self.assertEqual(publication['repository_version'], version_hrefs[-1])

        # Step 4
        publication = publish(self.cfg, publisher, repo, non_latest)

        # Step 5
        self.assertEqual(publication['repository_version'], non_latest)

        # Step 6
        with self.assertRaises(HTTPError):
            body = {
                'repository': repo['_href'],
                'repository_version': non_latest
            }
            self.client.post(urljoin(publisher['_href'], 'publish/'), body)


class SyncPublishReferencesUpdateTestCase(unittest.TestCase):
    """Sync/publish a repo that ``updateinfo.xml`` contains references."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Sync/publish a repo that ``updateinfo.xml`` contains references.

        This test targets the following issue:

        `Pulp #3998 <https://pulp.plan.io/issues/3998>`_.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        body = gen_rpm_remote(url=RPM_REFERENCES_UPDATEINFO_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertIsNotNone(repo['_latest_version_href'])

        content_summary = get_content_summary(repo)
        self.assertDictEqual(
            content_summary,
            RPM_FIXTURE_SUMMARY,
            content_summary
        )

        publisher = self.client.post(RPM_PUBLISHER_PATH, gen_rpm_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])

        publication = publish(self.cfg, publisher, repo)
        self.addCleanup(self.client.delete, publication['_href'])


class SyncPublishTestCase(unittest.TestCase):
    """Test sync and publish for different RPM repositories.

    This test targets the following issue:

    `Pulp #4108 <https://pulp.plan.io/issues/4108>`_.
    `Pulp #4134 <https://pulp.plan.io/issues/4134>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.page_handler)

    def test_rpm_rich_weak(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_RICH_WEAK_FIXTURE_URL)

    def test_rpm_long_updateinfo(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_LONG_UPDATEINFO_FIXTURE_URL)

    def test_rpm_alt_layout(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_ALT_LAYOUT_FIXTURE_URL)

    def test_rpm_sha512(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_SHA512_FIXTURE_URL)

    def test_srpm(self):
        """Sync and publish a SRPM repository. See :meth: `do_test`."""
        self.do_test(SRPM_UNSIGNED_FIXTURE_URL)

    def test_drpm(self):
        """Sync and publish a DRPM repository. See :meth: `do_test`."""
        self.do_test(DRPM_UNSIGNED_FIXTURE_URL)

    def do_test(self, url):
        """Sync and publish an RPM repository given a feed URL."""
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        remote = self.client.post(RPM_REMOTE_PATH, gen_rpm_remote(url=url))
        self.addCleanup(self.client.delete, remote['_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertIsNotNone(repo['_latest_version_href'])

        publisher = self.client.post(RPM_PUBLISHER_PATH, gen_rpm_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])

        publication = publish(self.cfg, publisher, repo)
        self.addCleanup(self.client.delete, publication['_href'])
