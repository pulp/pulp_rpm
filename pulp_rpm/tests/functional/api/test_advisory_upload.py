"""Tests that perform actions over advisory content unit upload."""
import pytest
import os
import json
from tempfile import NamedTemporaryFile

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_rpm.tests.functional.constants import (
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_PACKAGE_FILENAME,
)

from pulpcore.client.pulp_rpm.exceptions import ApiException


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


@pytest.fixture
def upload_wrong_file_type(rpm_advisory_api, http_get):
    def _upload(remote_path):
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(http_get(remote_path))
            upload_attrs = {
                "file": file_to_upload.name,
            }
            return rpm_advisory_api.create(**upload_attrs)

    return _upload


@pytest.fixture
def upload_advisory_json(rpm_advisory_api):
    def _upload(advisory=BASE_TEST_JSON, repository=None):
        """Upload advisory from a json file."""
        with NamedTemporaryFile("w+") as file_to_upload:
            json.dump(json.loads(advisory), file_to_upload)
            upload_attrs = {
                "file": file_to_upload.name,
            }
            if repository:
                upload_attrs["repository"] = repository.pulp_href

            file_to_upload.flush()
            return rpm_advisory_api.create(**upload_attrs)

    return _upload


@pytest.fixture
def assert_uploaded_advisory(rpm_advisory_api):
    def _from_results(response, advisory_id):
        assert 2 == len(response.created_resources)
        vers_href = None
        for rsrc in response.created_resources:
            if "versions" in rsrc:
                vers_href = rsrc
        advisories = rpm_advisory_api.list(id=advisory_id, repository_version=vers_href)
        assert 1 == len(advisories.results)
        return advisories.results[0].pulp_href, vers_href

    return _from_results


def test_upload_wrong_type(upload_wrong_file_type, delete_orphans_pre):
    """Test that a proper error is raised when wrong file content type is uploaded."""
    bad_file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)
    with pytest.raises(ApiException) as e:
        upload_wrong_file_type(bad_file_to_use)
    assert "JSON" in e.value.body


def test_upload_json(upload_advisory_json, rpm_advisory_api, monitor_task, delete_orphans_pre):
    """Test upload advisory from JSON file."""
    upload = upload_advisory_json()
    content = monitor_task(upload.task).created_resources[0]
    advisory = rpm_advisory_api.read(content)
    assert advisory.id == "RHSA-XXXX:XXXX"


def test_merging(
    upload_advisory_json,
    assert_uploaded_advisory,
    rpm_advisory_api,
    rpm_repository_factory,
    monitor_task,
    delete_orphans_pre,
):
    """Test the 'same' advisory, diff pkglists, into a repo, expecting a merged package-list."""
    repo = rpm_repository_factory()
    upload = upload_advisory_json(advisory=BEAR_JSON, repository=repo)
    task_response = monitor_task(upload.task)
    advisory_href, vers_href = assert_uploaded_advisory(task_response, "CEBA-2019--666")
    assert vers_href == f"{repo.pulp_href}versions/1/"
    bear = rpm_advisory_api.read(advisory_href)
    assert "CEBA-2019--666" == bear.id  # Is this suppose to be an equal comparison?
    assert 1 == len(bear.pkglist)
    assert 1 == len(bear.pkglist[0].packages)

    # Second upload, no pkg-intersection - add both collections
    # NOTE: also check that unnamed-collections are now named "collection_N", so
    # they can be uniquely identified
    upload = upload_advisory_json(advisory=CAMEL_JSON, repository=repo)
    task_response = monitor_task(upload.task)
    advisory_href, vers_href = assert_uploaded_advisory(task_response, "CEBA-2019--666")
    assert vers_href == f"{repo.pulp_href}versions/2/"
    cambear = rpm_advisory_api.read(advisory_href)
    assert "CEBA-2019--666" == cambear.id
    assert 2 == len(cambear.pkglist)
    coll_names = [row.name for row in cambear.pkglist]
    assert "collection_0" in coll_names
    assert "collection_1" in coll_names
    assert 1 == len(cambear.pkglist[0].packages)
    assert 1 == len(cambear.pkglist[1].packages)
    names = [plist.packages[0]["name"] for plist in cambear.pkglist]
    assert "camel" in names
    assert "bear" in names

    # Third upload, two pkgs, intersects with existing, expect AdvisoryConflict failure
    upload = upload_advisory_json(advisory=CAMEL_BIRD_JSON, repository=repo)
    with pytest.raises(PulpTaskError) as ctx:
        task_response = monitor_task(upload.task)
    assert "neither package list is a proper subset of the other" in str(ctx.value)
    assert "ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION" in str(ctx.value)

    # Fourth upload, intersecting pkglists, expecting three pkgs
    upload = upload_advisory_json(advisory=CAMEL_BEAR_DOG_JSON, repository=repo)
    task_response = monitor_task(upload.task)
    advisory_href, vers_href = assert_uploaded_advisory(task_response, "CEBA-2019--666")
    assert vers_href == f"{repo.pulp_href}versions/3/"
    cambeardog = rpm_advisory_api.read(advisory_href)
    assert "CEBA-2019--666" == cambeardog.id
    assert 1 == len(cambeardog.pkglist)
    # Expect one collection, not a merge
    names = [pkg["name"] for pkg in cambeardog.pkglist[0].packages]
    assert 3 == len(names)
    assert "camel" in names
    assert "bear" in names
    assert "dog" in names


def test_8683_error_path(
    upload_advisory_json,
    assert_uploaded_advisory,
    rpm_advisory_api,
    rpm_repository_factory,
    monitor_task,
    delete_orphans_pre,
):
    """
    Test that upload-fail doesn't break all future uploads.

    See https://pulp.plan.io/issues/8683 for details.
    """
    # Upload an advisory
    repo = rpm_repository_factory()
    upload = upload_advisory_json(advisory=CESA_2020_5002, repository=repo)
    task_response = monitor_task(upload.task)
    assert_uploaded_advisory(task_response, "TEST-CESA-2020:5002")

    # Try to upload it 'again' and watch it fail
    with pytest.raises(PulpTaskError):
        upload = upload_advisory_json(advisory=CESA_2020_5002, repository=repo)
        monitor_task(upload.task)

    # Upload a different advisory and Don't Fail
    upload = upload_advisory_json(advisory=CESA_2020_4910, repository=repo)
    task_response = monitor_task(upload.task)
    advisory_href, vers_href = assert_uploaded_advisory(task_response, "TEST-CESA-2020:4910")
    advisory = rpm_advisory_api.read(advisory_href)
    # Make sure the second advisory was persisted
    assert "TEST-CESA-2020:4910" == advisory.id
