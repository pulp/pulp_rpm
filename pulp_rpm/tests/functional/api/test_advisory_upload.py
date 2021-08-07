"""Tests that perform actions over advisory content unit upload."""
import os
import json
from tempfile import NamedTemporaryFile

from pulp_smash import api, config

from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTaskError,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo
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

    CESA_2020_5002 = """{
        "title": "Moderate CentOS curl Security Update",
        "type": "security",
        "description": "",
        "release": "el7",
        "version": "1",
        "severity": "Moderate",
        "status": "final",
        "updated": "2020-11-18 17:30:30",
        "issued": "2020-11-18 17:30:30",
        "pkglist": [
            {
              "packages": [
                {
                  "arch": "x86_64",
                  "epoch": "0",
                  "filename": "curl-7.29.0-59.el7_9.1.x86_64.rpm",
                  "release": "59.el7_9.1",
                  "name": "curl",
                  "sum": "dfc95bdd8057839d4b45153318acb4e09f4da257afee1c57c07781870a68ecef",
                  "sum_type": "sha256"
                },
                {
                  "arch": "i686",
                  "epoch": "0",
                  "filename": "libcurl-7.29.0-59.el7_9.1.i686.rpm",
                  "release": "59.el7_9.1",
                  "name": "libcurl",
                  "sum": "3054ca1c0cc8eef5f08ce1d3be56c7a39e97d92361e8bd265bea14d06f590219",
                  "sum_type": "sha256"
                },
                {
                  "arch": "x86_64",
                  "epoch": "0",
                  "filename": "libcurl-7.29.0-59.el7_9.1.x86_64.rpm",
                  "release": "59.el7_9.1",
                  "name": "libcurl",
                  "sum": "4ad0b71e3a6468fba1b43ab82fad024415b5296c7b77d1348fb9afa3f828f98e",
                  "sum_type": "sha256"
                },
                {
                  "arch": "i686",
                  "epoch": "0",
                  "filename": "libcurl-devel-7.29.0-59.el7_9.1.i686.rpm",
                  "release": "59.el7_9.1",
                  "name": "libcurl-devel",
                  "sum": "7ab4f1b0aa285d3773fdbd8bfc529969ca101a627d3ea88bea1f99a42093e132",
                  "sum_type": "sha256"
                },
                {
                  "arch": "x86_64",
                  "epoch": "0",
                  "filename": "libcurl-devel-7.29.0-59.el7_9.1.x86_64.rpm",
                  "release": "59.el7_9.1",
                  "name": "libcurl-devel",
                  "sum": "f92fde3f97c0034135796baa7cd55f87c0550a88ac79adbdcc9c7f64c595614b",
                  "sum_type": "sha256"
                }
              ]
            }
            ],
            "id": "TEST-CESA-2020:5002",
            "from": "centos-announce@centos.org",
            "references": [
            {
              "href": "https://access.redhat.com/errata/RHSA-2020:5002",
              "ref_id": "CESA-2020:5002",
              "title": "Moderate CentOS curl Security Update",
              "ref_type": "security"
            },
            {
              "href": "https://lists.centos.org/pipermail/centos-announce/2020-November/035840.html",
              "ref_id": "CESA-2020:5002",
              "title": "Moderate CentOS curl Security Update",
              "ref_type": "security"
            }
        ]
    }"""  # noqa

    CESA_2020_4910 = """{
        "title": "Important CentOS xorg-x11-server Security Update",
        "type": "security",
        "description": "",
        "release": "el7",
        "version": "1",
        "severity": "Important",
        "status": "final",
        "updated": "2020-11-06 22:19:48",
        "issued": "2020-11-06 22:19:48",
        "pkglist": [
            {
                "packages": [
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-Xdmx-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-Xdmx",
                      "sum": "0435f345b2b188c76dbb4a538bf0f878834a41e723491df1926231020fd88efd",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-Xephyr-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-Xephyr",
                      "sum": "2d21d53b305e30b058ca88d8778bda67000a5d52ab320f04b35e63f6a78f2163",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-Xnest-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-Xnest",
                      "sum": "51fbacc2e26050a7772549f1fe16c46bd8063ea187825ad89b237c34fa9b4250",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-Xorg-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-Xorg",
                      "sum": "eb89964d5fd40ec94ee8db97a5a14cc8dd6329b83d82ab29ee1a595653ce5223",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-Xvfb-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-Xvfb",
                      "sum": "ea32b047fba7fd327bf943da2a18413a1ed3e245cc1b077f34d1c8f6048d9813",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-Xwayland-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-Xwayland",
                      "sum": "4a6ffb39008edd469d4365bb3bf858f5f5f466129eb9e330d978b28866906891",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-common-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-common",
                      "sum": "339bcf68cb37a454eddff7218aff4153a36bafc0d36e2b5b6bde8311c6f3eed8",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "i686",
                      "epoch": "0",
                      "filename": "xorg-x11-server-devel-1.20.4-12.el7_9.i686.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-devel",
                      "sum": "55e13fc8624f8a63b785b5194281c38a4670f03113b0ff2b8fc1df1ca473e1e8",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "x86_64",
                      "epoch": "0",
                      "filename": "xorg-x11-server-devel-1.20.4-12.el7_9.x86_64.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-devel",
                      "sum": "e2dd0c67f3d88a9506f72fcc21ec0af786a377befabac8e1670d3e012d844b06",
                      "sum_type": "sha256"
                    },
                    {
                      "arch": "noarch",
                      "epoch": "0",
                      "filename": "xorg-x11-server-source-1.20.4-12.el7_9.noarch.rpm",
                      "release": "12.el7_9",
                      "name": "xorg-x11-server-source",
                      "sum": "1baa9cb2d4f8d4300ac333fbc7bc130dce9145c67aea3bd6efa4a0354fc92b6d",
                      "sum_type": "sha256"
                    }
                ]
            }
        ],
        "id": "TEST-CESA-2020:4910",
        "from": "centos-announce@centos.org",
        "references": [
            {
              "href": "https://access.redhat.com/errata/RHSA-2020:4910",
              "ref_id": "CESA-2020:4910",
              "title": "Important CentOS xorg-x11-server Security Update",
              "ref_type": "security"
            },
            {
              "href": "https://lists.centos.org/pipermail/centos-cr-announce/2020-November/012889.html",
              "ref_id": "CESA-2020:4910",
              "title": "Important CentOS xorg-x11-server Security Update",
              "ref_type": "security"
            }
        ]
    }"""  # noqa

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

    def test_8683_error_path(self):
        """
        Test that upload-fail doesn't break all future uploads.

        See https://pulp.plan.io/issues/8683 for details.
        """
        # Upload an advisory
        advisory_str = self.CESA_2020_5002
        upload = self.do_test_json(advisory=advisory_str, repository=self.repo)
        task_response = monitor_task(upload.task)
        self._from_results(task_response, "TEST-CESA-2020:5002")

        # Try to upload it 'again' and watch it fail
        with self.assertRaises(PulpTaskError):
            upload = self.do_test_json(advisory=self.CESA_2020_5002, repository=self.repo)
            monitor_task(upload.task)

        # Upload a different advisory and Don't Fail
        advisory_str = self.CESA_2020_4910
        upload = self.do_test_json(advisory=advisory_str, repository=self.repo)
        task_response = monitor_task(upload.task)
        advisory_href, vers_href = self._from_results(task_response, "TEST-CESA-2020:4910")
        advisory = self.content_api.read(advisory_href)
        # Make sure the second advisory was persisted
        self.assertEqual("TEST-CESA-2020:4910", advisory.id)

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
