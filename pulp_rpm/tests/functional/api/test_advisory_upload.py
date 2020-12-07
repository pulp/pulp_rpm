# coding=utf-8
"""Tests that perform actions over advisory content unit upload."""
import os
import json
from tempfile import NamedTemporaryFile

from pulp_smash import api, config

from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import delete_orphans
from pulp_smash.utils import http_get

from pulp_rpm.tests.functional.utils import (
    core_client,
    gen_rpm_client,
)
from pulp_rpm.tests.functional.constants import (
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_PACKAGE_FILENAME,
)

from pulpcore.client.pulpcore import TasksApi
from pulpcore.client.pulp_rpm import ContentAdvisoriesApi
from pulpcore.client.pulp_rpm.exceptions import ApiException


class AdvisoryContentUnitTestCase(PulpTestCase):
    """
    Create and upload advisory content unit.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)
        delete_orphans()
        rpm_client = gen_rpm_client()
        cls.tasks_api = TasksApi(core_client)
        cls.content_api = ContentAdvisoriesApi(rpm_client)
        cls.bad_file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)

    def tearDown(self):
        """TearDown."""
        delete_orphans()

    def test_upload_wrong_type(self):
        """Test that a proper error is raised when wrong file content type is uploaded."""
        with self.assertRaises(ApiException) as e:
            self.do_test(self.bad_file_to_use)
        self.assertTrue("JSON" in e.exception.body)

    def test_upload_json(self):
        """Test upload advisory from JSON file."""
        upload = self.do_test_json()
        content = monitor_task(upload.task).created_resources[0]
        advisory = self.content_api.read(content)
        self.assertTrue(advisory.id == "RHSA-XXXX:XXXX")

    def do_test(self, remote_path):
        """Upload wrong type of the file."""
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(http_get(remote_path))
            upload_attrs = {
                "file": file_to_upload.name,
            }
            return self.content_api.create(**upload_attrs)

    def do_test_json(self):
        """Upload advisory from a json file."""
        advisory = """{
        "updated": "2014-09-28 00:00:00",
        "issued": "2014-09-24 00:00:00",
        "id": "RHSA-XXXX:XXXX"}"""

        with NamedTemporaryFile("w+") as file_to_upload:
            json.dump(json.loads(advisory), file_to_upload)
            upload_attrs = {
                "file": file_to_upload.name,
            }
            file_to_upload.flush()
            return self.content_api.create(**upload_attrs)
