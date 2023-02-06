"""Tests that perform actions over content unit."""
import requests

from urllib.parse import urljoin

from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTaskError,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo, get_content

from pulp_rpm.tests.functional.utils import (
    gen_artifact,
    gen_rpm_client,
    gen_rpm_content_attrs,
    gen_rpm_remote,
    skip_if,
)
from pulp_rpm.tests.functional.constants import (
    RPM_KICKSTART_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_REPO_METADATA_FIXTURE_URL,
    RPM_PACKAGE_FILENAME,
    RPM_PACKAGE_FILENAME2,
    RPM_SIGNED_URL,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    Configuration,
    ContentPackagesApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
)


class ContentUnitTestCase(PulpTestCase):
    """CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp #3445 <https://pulp.plan.io/issues/3445>`_
    * `Pulp Smash #870 <https://github.com/pulp/pulp-smash/issues/870>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        delete_orphans()
        cls.content_unit = {}
        cls.rpm_content_api = ContentPackagesApi(gen_rpm_client())
        cls.artifact = gen_artifact(RPM_SIGNED_URL)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        delete_orphans()

    def test_01_create_content_unit(self):
        """Create content unit."""
        attrs = gen_rpm_content_attrs(self.artifact, RPM_PACKAGE_FILENAME)
        response = self.rpm_content_api.create(**attrs)
        # rpm package doesn't keep relative_path but the location href
        del attrs["relative_path"]
        created_resources = monitor_task(response.task).created_resources
        content_unit = self.rpm_content_api.read(created_resources[0])
        self.content_unit.update(content_unit.to_dict())
        for key, val in attrs.items():
            with self.subTest(key=key):
                self.assertEqual(self.content_unit[key], val)

    @skip_if(bool, "content_unit", False)
    def test_02_read_content_unit(self):
        """Read a content unit by its href."""
        content_unit = self.rpm_content_api.read(self.content_unit["pulp_href"]).to_dict()
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(content_unit[key], val)

    @skip_if(bool, "content_unit", False)
    def test_02_read_content_units(self):
        """Read a content unit by its pkg_id."""
        page = self.rpm_content_api.list(pkg_id=self.content_unit["pkg_id"])
        self.assertEqual(len(page.results), 1)
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(page.results[0].to_dict()[key], val)

    @skip_if(bool, "content_unit", False)
    def test_03_partially_update(self):
        """Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = gen_rpm_content_attrs(self.artifact, RPM_PACKAGE_FILENAME2)
        with self.assertRaises(AttributeError) as exc:
            self.rpm_content_api.partial_update(self.content_unit["pulp_href"], attrs)
        msg = "object has no attribute 'partial_update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_03_fully_update(self):
        """Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = gen_rpm_content_attrs(self.artifact, RPM_PACKAGE_FILENAME2)
        with self.assertRaises(AttributeError) as exc:
            self.rpm_content_api.update(self.content_unit["pulp_href"], attrs)
        msg = "object has no attribute 'update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_04_delete(self):
        """Attempt to delete a content unit using HTTP DELETE.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        with self.assertRaises(AttributeError) as exc:
            self.rpm_content_api.delete(self.content_unit["pulp_href"])
        msg = "object has no attribute 'delete'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_05_duplicate_raise_error(self):
        """Attempt to create duplicate package."""
        attrs = gen_rpm_content_attrs(self.artifact, RPM_PACKAGE_FILENAME)
        response = self.rpm_content_api.create(**attrs)
        with self.assertRaises(PulpTaskError) as cm:
            monitor_task(response.task)
        task_result = cm.exception.task.to_dict()
        msg = "There is already a package with"
        self.assertTrue(msg in task_result["error"]["description"])


class ContentUnitRemoveTestCase(PulpTestCase):
    """
    Test of content removal.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        delete_orphans()
        cls.client = gen_rpm_client()
        cls.cfg = Configuration(cls.client)
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)

    def do_test_remove_unit(self, remote_url):
        """
        Sync repository and test that content can't be removed directly.
        """
        repo = self.repo_api.create(gen_repo())
        remote_body = gen_rpm_remote(remote_url, policy="on_demand")
        remote = self.remote_api.create(remote_body)
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)

        # add resources to clean up
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # Test remove content by types contained in repository.
        repo_content = get_content(repo.to_dict())
        base_addr = self.cfg.get_host_settings()[0]["url"]

        for content_type in repo_content.keys():
            response = requests.delete(
                urljoin(base_addr, repo_content[content_type][0]["pulp_href"])
            )
            # check that '405' (method not allowed) is returned
            self.assertEqual(response.status_code, 405)

    def test_all(self):
        """
        Test three repositories to cover RPM content types.

        - advisory
        - distribution_tree
        - modulemd
        - modulemd_defaults
        - package
        - packagecategory
        - packageenvironment
        - packagegroup
        - packagelangpacks
        - repo metadata
        """
        self.do_test_remove_unit(RPM_MODULAR_FIXTURE_URL)
        self.do_test_remove_unit(RPM_KICKSTART_FIXTURE_URL)
        self.do_test_remove_unit(RPM_REPO_METADATA_FIXTURE_URL)
