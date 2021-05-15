"""Tests that perform actions over advisory content unit upload."""
import os
import json
from tempfile import NamedTemporaryFile

from pulp_smash import api, config

from pulp_smash.pulp3.bindings import PulpTaskError, PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import delete_orphans, gen_repo
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
from pulpcore.client.pulp_rpm import ContentAdvisoriesApi, RepositoriesRpmApi
from pulpcore.client.pulp_rpm.exceptions import ApiException


class AdvisoryContentUnitTestCase(PulpTestCase):
    """
    Create and upload advisory content unit.
    """

    BASE_TEST_JSON = """{
        "updated": "2014-09-28 00:00:00",
        "issued": "2014-09-24 00:00:00",
        "id": "RHSA-XXXX:XXXX",
         "pkglist": [
           {
            "packages": [
             {
              "arch": "noarch",
              "epoch": "0",
              "filename": "bear-4.1-1.noarch.rpm",
              "name": "bear",
              "reboot_suggested": false,
              "relogin_suggested": false,
              "restart_suggested": false,
              "release": "1",
              "src": "http://www.fedoraproject.org",
              "sum": "",
              "sum_type": "",
              "version": "4.1"
             }
            ]
           }
         ],
         "severity":  "",
         "description":  "Not available",
         "reboot_suggested":  false,
         "solution":  "Not available",
         "fromstr":  "centos-announce@centos.org"}"""

    BEAR_JSON = """{
        "issued":  "2020-03-08 20:04:01",
        "id":  "CEBA-2019--666",
        "type":  "Bug Fix Advisory",
        "release":  "1",
        "version": "1",
        "pkglist": [
            {
                "packages": [
                    {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "bear-4.1-1.noarch.rpm",
                        "name": "bear",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "1",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "4.1"
                    }
                ]
            }
        ],
        "severity":  "",
        "description":  "Not available",
        "reboot_suggested":  false,
        "updated":  "2020-03-08 20:04:01",
        "solution":  "Not available",
        "fromstr":  "centos-announce@centos.org"
    }"""

    CAMEL_JSON = """{
        "issued":  "2020-03-08 20:04:01",
        "id":  "CEBA-2019--666",
        "type":  "Bug Fix Advisory",
        "release":  "1",
        "version": "1",
        "pkglist": [
            {
                "packages": [
                    {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "camel-0.1-1.noarch.rpm",
                        "name": "camel",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "1",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "0.1"
                    }
                ]
            }
        ],
        "severity":  "",
        "description":  "Not available",
        "reboot_suggested":  false,
        "updated":  "2020-03-08 20:04:01",
        "solution":  "Not available",
        "fromstr":  "centos-announce@centos.org"
    }"""

    CAMEL_BIRD_JSON = """{
        "issued":  "2020-03-08 20:04:01",
        "id":  "CEBA-2019--666",
        "type":  "Bug Fix Advisory",
        "release":  "1",
        "version": "1",
        "pkglist": [
            {
                "packages": [
                    {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "camel-0.1-1.noarch.rpm",
                        "name": "camel",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "1",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "0.1"
                    },
                    {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "bird-1.2-3.noarch.rpm",
                        "name": "bird",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "3",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "1.2"
                    }
                ]
            }
        ],
        "severity":  "",
        "description":  "Not available",
        "reboot_suggested":  false,
        "updated":  "2020-03-08 20:04:01",
        "solution":  "Not available",
        "fromstr":  "centos-announce@centos.org"
    }"""

    CAMEL_BEAR_DOG_JSON = """{
        "issued":  "2020-03-08 20:04:01",
        "id":  "CEBA-2019--666",
        "type":  "Bug Fix Advisory",
        "release":  "1",
        "version": "1",
        "pkglist": [
            {
                "packages": [
                    {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "camel-0.1-1.noarch.rpm",
                        "name": "camel",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "1",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "0.1"
                    },
                                        {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "bear-4.1-1.noarch.rpm",
                        "name": "bear",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "1",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "4.1"
                    },
                    {
                        "arch": "noarch",
                        "epoch": "0",
                        "filename": "dog-6.1-6.noarch.rpm",
                        "name": "dog",
                        "reboot_suggested": false,
                        "relogin_suggested": false,
                        "restart_suggested": false,
                        "release": "6",
                        "src": "http://www.fedoraproject.org",
                        "sum": "",
                        "sum_type": "",
                        "version": "6.1"
                    }
                ]
            }
        ],
        "severity":  "",
        "description":  "Not available",
        "reboot_suggested":  false,
        "updated":  "2020-03-08 20:04:01",
        "solution":  "Not available",
        "fromstr":  "centos-announce@centos.org"
    }"""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)
        delete_orphans()
        cls.rpm_client = gen_rpm_client()
        cls.tasks_api = TasksApi(core_client)
        cls.content_api = ContentAdvisoriesApi(cls.rpm_client)
        cls.bad_file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)

    def setUp(self):
        """Per-test setup."""
        self.repo_api = RepositoriesRpmApi(self.rpm_client)
        self.repo = self.repo_api.create(gen_repo())
        self.assertEqual(self.repo.latest_version_href, f"{self.repo.pulp_href}versions/0/")

    def tearDown(self):
        """TearDown."""
        self.repo_api.delete(self.repo.pulp_href)
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

    def test_merging(self):
        """Test the 'same' advisory, diff pkglists, into a repo, expecting a merged package-list."""
        upload = self.do_test_json(advisory=self.BEAR_JSON, repository=self.repo)
        task_response = monitor_task(upload.task)
        advisory_href, vers_href = self._from_results(task_response, "CEBA-2019--666")
        self.assertEqual(vers_href, f"{self.repo.pulp_href}versions/1/")
        bear = self.content_api.read(advisory_href)
        self.assertTrue("CEBA-2019--666", bear.id)
        self.assertEqual(1, len(bear.pkglist))
        self.assertEqual(1, len(bear.pkglist[0].packages))

        # Second upload, no pkg-intersection - add both collections
        # NOTE: also check that unnamed-collections are now named "collection_N", so
        # they can be uniquely identified
        upload = self.do_test_json(advisory=self.CAMEL_JSON, repository=self.repo)
        task_response = monitor_task(upload.task)
        advisory_href, vers_href = self._from_results(task_response, "CEBA-2019--666")
        self.assertEqual(vers_href, f"{self.repo.pulp_href}versions/2/")
        cambear = self.content_api.read(advisory_href)
        self.assertEqual("CEBA-2019--666", cambear.id)
        self.assertEqual(2, len(cambear.pkglist))
        coll_names = [row.name for row in cambear.pkglist]
        self.assertTrue("collection_0" in coll_names)
        self.assertTrue("collection_1" in coll_names)
        self.assertEqual(1, len(cambear.pkglist[0].packages))
        self.assertEqual(1, len(cambear.pkglist[1].packages))
        names = [plist.packages[0]["name"] for plist in cambear.pkglist]
        self.assertTrue("camel" in names)
        self.assertTrue("bear" in names)

        # Third upload, two pkgs, intersects with existing, expect AdvisoryConflict failure
        upload = self.do_test_json(advisory=self.CAMEL_BIRD_JSON, repository=self.repo)
        with self.assertRaises(PulpTaskError) as ctx:
            task_response = monitor_task(upload.task)
        self.assertTrue(
            "neither package list is a proper subset of the other" in str(ctx.exception)
        )
        self.assertTrue("ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION" in str(ctx.exception))

        # Fourth upload, intersecting pkglists, expecting three pkgs
        upload = self.do_test_json(advisory=self.CAMEL_BEAR_DOG_JSON, repository=self.repo)
        task_response = monitor_task(upload.task)
        advisory_href, vers_href = self._from_results(task_response, "CEBA-2019--666")
        self.assertEqual(vers_href, f"{self.repo.pulp_href}versions/3/")
        cambeardog = self.content_api.read(advisory_href)
        self.assertEqual("CEBA-2019--666", cambeardog.id)
        self.assertEqual(1, len(cambeardog.pkglist))
        # Expect one collection, not a merge
        names = [pkg["name"] for pkg in cambeardog.pkglist[0].packages]
        self.assertEqual(3, len(names))
        self.assertTrue("camel" in names)
        self.assertTrue("bear" in names)
        self.assertTrue("dog" in names)

    def _from_results(self, response, advisory_id):
        self.assertEqual(2, len(response.created_resources))
        vers_href = None
        for rsrc in response.created_resources:
            if "versions" in rsrc:
                vers_href = rsrc
        advisories = self.content_api.list(id=advisory_id, repository_version=vers_href)
        self.assertEqual(1, len(advisories.results))
        return advisories.results[0].pulp_href, vers_href

    def do_test(self, remote_path):
        """Upload wrong type of the file."""
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(http_get(remote_path))
            upload_attrs = {
                "file": file_to_upload.name,
            }
            return self.content_api.create(**upload_attrs)

    def do_test_json(self, advisory=BASE_TEST_JSON, repository=None):
        """Upload advisory from a json file."""
        with NamedTemporaryFile("w+") as file_to_upload:
            json.dump(json.loads(advisory), file_to_upload)
            upload_attrs = {
                "file": file_to_upload.name,
            }
            if repository:
                upload_attrs["repository"] = repository.pulp_href

            file_to_upload.flush()
            return self.content_api.create(**upload_attrs)
