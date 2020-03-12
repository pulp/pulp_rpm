# coding=utf-8
"""Tests that perform actions over content unit."""
import unittest

from pulp_smash.pulp3.utils import delete_orphans, gen_repo

from pulp_rpm.tests.functional.utils import (
    gen_artifact,
    gen_rpm_client,
    gen_rpm_content_attrs,
    monitor_task,
    skip_if,
)
from pulp_rpm.tests.functional.constants import (
    RPM_SIGNED_URL,
    RPM_PACKAGE_FILENAME,
    RPM_PACKAGE_FILENAME2,
    RPM_SIGNED_URL2
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import ContentPackagesApi, RepositoriesRpmApi


class ContentUnitTestCase(unittest.TestCase):
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
        del attrs['relative_path']
        created_resources = monitor_task(response.task)
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
        task_result = monitor_task(response.task)
        msg = "There is already a package with"
        self.assertTrue(msg in task_result['error']['description'])

    def test_06_second_unit_raises_error(self):
        """
        Create a duplicate content unit with different ``artifacts`` and same ``repo_key_fields``.
        """
        delete_orphans()
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        artifact = gen_artifact()

        # create first content unit.
        content_attrs = {"artifact": artifact["pulp_href"], "relative_path": "test_package"}
        response = self.rpm_content_api.create(**content_attrs)
        monitor_task(response.task)

        artifact = gen_artifact(url=RPM_SIGNED_URL2)

        # create second content unit.
        second_content_attrs = {"artifact": artifact["pulp_href"]}
        second_content_attrs["relative_path"] = content_attrs["relative_path"]
        response = self.rpm_content_api.create(**second_content_attrs)
        monitor_task(response.task)

        data = {"add_content_units": [c.pulp_href for c in self.rpm_content_api.list().results]}
        response = repo_api.modify(repo.pulp_href, data)
        task = monitor_task(response.task)

        error_message = "Cannot create repository version. Path is duplicated: {}.".format(
            content_attrs["relative_path"]
        )

        self.assertEqual(task["error"]["description"], error_message)
