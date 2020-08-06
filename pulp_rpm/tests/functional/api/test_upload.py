# coding=utf-8
"""Tests that perform actions over content unit."""
import os
from tempfile import NamedTemporaryFile

from pulp_smash.pulp3.bindings import PulpTaskError, PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import delete_orphans
from pulp_smash.utils import http_get

from pulp_rpm.tests.functional.utils import (
    core_client,
    gen_rpm_client,
)
from pulp_rpm.tests.functional.constants import (
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_PACKAGE_FILENAME,
    RPM_WITH_NON_ASCII_URL
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulpcore import TasksApi
from pulpcore.client.pulp_rpm import ContentPackagesApi


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
        rpm_client = gen_rpm_client()
        cls.tasks_api = TasksApi(core_client)
        cls.content_api = ContentPackagesApi(rpm_client)
        cls.file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)

    def tearDown(self):
        """TearDown."""
        delete_orphans()

    def test_single_request_unit_and_duplicate_unit(self):
        """Test single request upload unit.

        1. Upload a unit
        2. Attempt to upload same unit
        """
        # Single unit upload
        upload = self.do_test(self.file_to_use)
        content = monitor_task(upload.task)[0]
        package = self.content_api.read(content)
        self.assertTrue(package.location_href == RPM_PACKAGE_FILENAME)

        # Duplicate unit
        upload = self.do_test(self.file_to_use)
        try:
            monitor_task(upload.task)
        except PulpTaskError:
            pass
        task_report = self.tasks_api.read(upload.task)
        msg = 'There is already a package with'
        self.assertTrue(msg in task_report.error['description'])

    def test_upload_non_ascii(self):
        """Test whether one can upload an RPM with non-ascii metadata."""
        packages_count = self.content_api.list().count
        upload = self.do_test(RPM_WITH_NON_ASCII_URL)
        monitor_task(upload.task)
        new_packages_count = self.content_api.list().count
        self.assertTrue((packages_count + 1) == new_packages_count)

    def do_test(self, remote_path):
        """Upload a Package and return Task of upload."""
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(
                http_get(remote_path)
            )
            upload_attrs = {
                'file': file_to_upload.name,
                'relative_path': RPM_PACKAGE_FILENAME
            }
            return self.content_api.create(**upload_attrs)
