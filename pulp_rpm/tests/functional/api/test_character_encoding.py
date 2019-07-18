# coding=utf-8
"""Tests for Pulp's characters encoding."""
import unittest

from pulp_smash import api, config, utils
from pulp_smash.pulp3.constants import ARTIFACTS_PATH, REPO_PATH
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_versions,
)
from requests.exceptions import HTTPError

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_WITH_NON_ASCII_NAME,
    RPM_WITH_NON_ASCII_URL,
    RPM_WITH_NON_UTF_8_NAME,
    RPM_WITH_NON_UTF_8_URL,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class UploadEncodingMetadataTestCase(unittest.TestCase):
    """Test upload of RPMs with different character encoding.

    This test targets the following issues:

    * `Pulp #4210 <https://pulp.plan.io/issues/4210>`_
    * `Pulp #4215 <https://pulp.plan.io/issues/4215>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        delete_orphans(cls.cfg)

    def test_upload_non_ascii(self):
        """Test whether one can upload an RPM with non-ascii metadata."""
        files = {'file': utils.http_get(RPM_WITH_NON_ASCII_URL)}
        artifact = self.client.post(ARTIFACTS_PATH, files=files)
        content_unit = self.client.post(RPM_CONTENT_PATH, {
            '_artifact': artifact['_href'],
            'relative_path': RPM_WITH_NON_ASCII_NAME
        })
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        repo_versions = get_versions(repo)
        self.assertEqual(len(repo_versions), 0, repo_versions)
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [content_unit['_href']]}
        )
        repo_versions = get_versions(repo)
        self.assertEqual(len(repo_versions), 1, repo_versions)

    def test_upload_non_utf8(self):
        """Test whether an exception is raised when non-utf-8 is uploaded."""
        files = {'file': utils.http_get(RPM_WITH_NON_UTF_8_URL)}
        artifact = self.client.post(ARTIFACTS_PATH, files=files)
        with self.assertRaises(HTTPError):
            self.client.post(RPM_CONTENT_PATH, {
                '_artifact': artifact['_href'],
                'relative_path': RPM_WITH_NON_UTF_8_NAME
            })
