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

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_WITH_NON_ASCII_NAME,
    RPM_WITH_NON_ASCII_URL,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class UploadEncodingMetadataTestCase(unittest.TestCase):
    """Test upload of RPMs with different character encoding.

    This test targets the following issues:

    * `Pulp #4210 <https://pulp.plan.io/issues/4210>`_
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
        self.do_test(RPM_WITH_NON_ASCII_URL, RPM_WITH_NON_ASCII_NAME)

    def do_test(self, url, filename):
        """Test whether one can upload an RPM."""
        files = {'file': utils.http_get(url)}
        artifact = self.client.post(ARTIFACTS_PATH, files=files)
        content_unit = self.client.post(RPM_CONTENT_PATH, {
            '_artifact': artifact['_href'],
            'filename': filename
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
