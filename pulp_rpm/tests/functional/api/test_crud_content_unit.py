# coding=utf-8
"""Tests that CRUD rpm content units."""
import copy
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, utils
from pulp_smash.exceptions import TaskReportError
from pulp_smash.pulp3.constants import ARTIFACTS_PATH
from pulp_smash.pulp3.utils import delete_orphans, gen_repo

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_PACKAGE_DATA,
    RPM_PACKAGE_FILENAME,
    RPM_SIGNED_URL,
    RPM_SIGNED_URL2,
    RPM_UNSIGNED_URL,
)
from pulp_rpm.tests.functional.utils import (
    gen_artifact,
    gen_rpm_client,
    monitor_task,
    skip_if,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    RepositoriesRpmApi,
    ContentPackagesApi,
)


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
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.content_unit = {}
        cls.client = api.Client(cls.cfg, api.json_handler)
        files = {'file': utils.http_get(RPM_SIGNED_URL)}
        cls.artifact = cls.client.post(ARTIFACTS_PATH, files=files)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        delete_orphans(cls.cfg)

    def test_01_create_content_unit(self):
        """Create content unit."""
        self.content_unit.update(
            self.client.using_handler(api.task_handler).post(RPM_CONTENT_PATH, {
                'artifact': self.artifact['pulp_href'],
                'relative_path': RPM_PACKAGE_FILENAME
            })
        )
        for key, val in RPM_PACKAGE_DATA.items():
            with self.subTest(key=key):
                self.assertEqual(self.content_unit[key], val)

    @skip_if(bool, 'content_unit', False)
    def test_02_read_content_unit(self):
        """Read a content unit by its href."""
        content_unit = self.client.get(self.content_unit['pulp_href'])
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(content_unit[key], val)

    @skip_if(bool, 'content_unit', False)
    def test_02_read_content_units(self):
        """Read a content unit by its pkgId."""
        page = self.client.get(RPM_CONTENT_PATH, params={
            'pkgId': self.content_unit['pkgId']
        })
        self.assertEqual(len(page['results']), 1)
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(page['results'][0][key], val)

    @skip_if(bool, 'content_unit', False)
    def test_03_partially_update(self):
        """Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = copy.deepcopy(RPM_PACKAGE_DATA)
        attrs.update({'name': utils.uuid4()})
        with self.assertRaises(HTTPError) as exc:
            self.client.patch(self.content_unit['pulp_href'], attrs)
        self.assertEqual(exc.exception.response.status_code, 405)

    @skip_if(bool, 'content_unit', False)
    def test_03_fully_update(self):
        """Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = copy.deepcopy(RPM_PACKAGE_DATA)
        attrs.update({'name': utils.uuid4()})
        with self.assertRaises(HTTPError) as exc:
            self.client.put(self.content_unit['pulp_href'], attrs)
        self.assertEqual(exc.exception.response.status_code, 405)

    @skip_if(bool, 'content_unit', False)
    def test_04_delete(self):
        """Attempt to delete a content unit using HTTP DELETE.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        with self.assertRaises(HTTPError) as exc:
            self.client.delete(self.content_unit['pulp_href'])
        self.assertEqual(exc.exception.response.status_code, 405)


class DuplicateContentUnit(unittest.TestCase):
    """Attempt to create a duplicate content unit.

    This test targets the following issues:

    *  `Pulp #4125 <https://pulp.plan.io/issue/4125>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    @classmethod
    def tearDownClass(cls):
        """Clean created resources."""
        delete_orphans(cls.cfg)

    def test_raise_error(self):
        """Create a duplicate content unit using same artifact and filename."""
        delete_orphans(self.cfg)
        files = {'file': utils.http_get(RPM_UNSIGNED_URL)}
        artifact = self.client.post(ARTIFACTS_PATH, files=files)
        attrs = {
            'artifact': artifact['pulp_href'],
            'relative_path': RPM_PACKAGE_FILENAME
        }

        # create first content unit.
        self.client.using_handler(api.task_handler).post(RPM_CONTENT_PATH, attrs)

        with self.assertRaises(TaskReportError) as ctx:
            # using the same attrs used to create the first content unit.
            api.Client(self.cfg, api.task_handler).post(
                RPM_CONTENT_PATH,
                attrs
            )

        keywords = (
            'name',
            'epoch',
            'version',
            'release',
            'arch',
            'checksum_type',
            'pkgId',
        )

        for key in keywords:
            self.assertIn(
                key.lower(),
                ctx.exception.task['error']['description'].lower(),
                ctx.exception.task['error']
            )

    def test_second_unit_raises_error(self):
        """
        Create a duplicate content unit with different ``artifacts`` and same ``repo_key_fields``.
        """
        delete_orphans()
        client = gen_rpm_client()
        packages_api = ContentPackagesApi(client)
        repo_api = RepositoriesRpmApi(client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        artifact = gen_artifact()

        # create first content unit.
        content_attrs = {"artifact": artifact["pulp_href"], "relative_path": "test_package"}
        response = packages_api.create(**content_attrs)
        monitor_task(response.task)

        artifact = gen_artifact(url=RPM_SIGNED_URL2)

        # create second content unit.
        second_content_attrs = {"artifact": artifact["pulp_href"]}
        second_content_attrs["relative_path"] = content_attrs["relative_path"]
        response = packages_api.create(**second_content_attrs)
        monitor_task(response.task)

        data = {"add_content_units": [c.pulp_href for c in packages_api.list().results]}
        response = repo_api.modify(repo.pulp_href, data)
        task = monitor_task(response.task)

        error_message = "Cannot create repository version. Path is duplicated: {}.".format(
            content_attrs["relative_path"]
        )

        self.assertEqual(task["error"]["description"], error_message)
