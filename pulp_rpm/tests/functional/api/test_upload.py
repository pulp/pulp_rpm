# coding=utf-8
"""Tests that verify upload of content to Pulp."""
import hashlib
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.pulp3.constants import ARTIFACTS_PATH, BASE_PATH, REPO_PATH
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
)

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
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
        repo = client.post(REPO_PATH, gen_repo())

        self.addCleanup(client.delete, repo['_href'])
        client.post(
            urljoin(BASE_PATH, 'rpm/upload/'),
            files=file,
            data={'repository': repo['_href']}
        )
        repo = client.get(repo['_href'])

        # Assertion about repo version.
        self.assertIsNotNone(repo['_latest_version_href'], repo)

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
