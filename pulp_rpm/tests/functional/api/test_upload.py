# coding=utf-8
"""Tests that verify upload of content to Pulp."""
import hashlib
import unittest

from pulp_smash import api, config, utils
from pulp_smash.exceptions import TaskReportError
from pulp_smash.pulp3.constants import ARTIFACTS_PATH
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
)

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_PACKAGE_FILENAME,
    RPM_REPO_PATH,
    RPM_SINGLE_REQUEST_UPLOAD,
    RPM_UNSIGNED_URL,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SingleRequestUploadTestCase(unittest.TestCase):
    """Test whether one can upload a RPM using a single request.

    This test targets the following issues:

    `Pulp #4087 <https://pulp.plan.io/issues/4087>`_
    `Pulp #4285 <https://pulp.plan.io/issues/4285>`_
    """

    def test_single_request_upload(self):
        """Test single request upload."""
        cfg = config.get_config()
        # Pulp does not support single request upload for a RPM already present
        # in Pulp.
        delete_orphans(cfg)
        file = {'file': utils.http_get(RPM_UNSIGNED_URL)}
        client = api.Client(cfg, api.page_handler)
        repo = client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])
        client.using_handler(api.task_handler).post(
            RPM_SINGLE_REQUEST_UPLOAD,
            files=file,
            data={'repository': repo['pulp_href'], "relative_path": RPM_PACKAGE_FILENAME}
        )
        repo = client.get(repo['pulp_href'])

        # Assertion about repo version.
        self.assertIsNotNone(repo['latest_version_href'], repo)

        # Assertions about artifcats.
        artifact = client.get(ARTIFACTS_PATH)
        self.assertEqual(len(artifact), 1, artifact)
        self.assertEqual(
            artifact[0]['sha256'],
            hashlib.sha256(file['file']).hexdigest(),
            artifact
        )

        # Assertion about content unit.
        content = client.get(RPM_CONTENT_PATH)
        self.assertEqual(len(content), 1, content)


class SingleRequestUploadDuplicateTestCase(unittest.TestCase):
    """Attempt to use single request upload for unit already in Pulp.

    This test targets the following issue:

    * `Pulp #4536 <https://pulp.plan.io/issues/4536>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.client = api.Client(cls.cfg, api.page_handler)
        cls.file = {'file': utils.http_get(RPM_UNSIGNED_URL)}

    def test_duplicate_unit(self):
        """Test single request upload for unit already present in Pulp."""
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])
        self.single_request_upload(repo)
        with self.assertRaises(TaskReportError) as ctx:
            self.single_request_upload(repo)
        for key in RPM_PACKAGE_FILENAME.split("-")[:-1]:
            self.assertIn(
                key,
                ctx.exception.task['error']['description'].lower(),
                ctx.exception.task['error']
            )

    def single_request_upload(self, repo):
        """Create single request upload."""
        self.client.using_handler(api.task_handler).post(
            RPM_SINGLE_REQUEST_UPLOAD,
            files=self.file,
            data={'repository': repo['pulp_href'], "relative_path": RPM_PACKAGE_FILENAME}
        )
