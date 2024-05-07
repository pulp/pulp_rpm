Upload Content
==============

.. _upload-workflow:

Content can be added to a repository not only by synchronizing from a remote source but also by
uploading.

Bulk Upload
-----------

Upload artifacts
****************

Using pulp-cli commands :

.. literalinclude:: ../_scripts/artifact_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/artifact.sh
   :language: bash

Artifact GET response:

.. code:: json

    {
        "file": "artifact/49/921db74808725e9228f6e8f4c25c65d81ba2382d5b97f26814b9fd80977402",
        "md5": "0c9013e04fa09f48d1996b3fb4c11724",
        "pulp_created": "2019-11-27T13:48:15.394730Z",
        "pulp_href": "/pulp/api/v3/artifacts/c3440ebb-99bc-44a0-915c-ee06cc5d4001/",
        "sha1": "183a50aa0d25fdd0faa6642e4a82ff8870f96656",
        "sha224": "9b199695812ff2fab161aaa7873920b12c743b8b32f37be926bce649",
        "sha256": "49921db74808725e9228f6e8f4c25c65d81ba2382d5b97f26814b9fd80977402",
        "sha384": "59b3d541c495abee3d0295ae87aadfb9fd20280757fd2373160120d8690435c23ae48aed4f60d8cf0713f9c4876f7ffa",
        "sha512": "eaf47a730d2397e1b58d813914b0bad2b61aa90e5fa0b58101e98654f84d3a30826c2b67f0de96c5690b2bbf5bf847fa5b9f0cfdb970d52b94b56a94d68ca7c2",
        "size": 2473
    }

Create content from artifacts
*****************************

Using pulp-cli commands :

.. literalinclude:: ../_scripts/package_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/package.sh
   :language: bash

Package GET response (after task complete):

.. code:: json

    {
        "arch": "noarch",
        "artifact": "/pulp/api/v3/artifacts/c3440ebb-99bc-44a0-915c-ee06cc5d4001/",
        "changelogs": [],
        "checksum_type": "sha256",
        "conflicts": [],
        "description": "A dummy package of fox",
        "enhances": [],
        "epoch": "0",
        "files": [
            [
                "",
                "/tmp/",
                "fox.txt"
            ]
        ],
        "location_base": "",
        "location_href": "fox-1.1-2.noarch.rpm",
        "name": "fox",
        "obsoletes": [],
        "pkgId": "49921db74808725e9228f6e8f4c25c65d81ba2382d5b97f26814b9fd80977402",
        "provides": [
            [
                "fox",
                "EQ",
                "0",
                "1.1",
                "2",
                false
            ]
        ],
        "pulp_created": "2019-11-27T13:48:16.462655Z",
        "pulp_href": "/pulp/api/v3/content/rpm/packages/9ee09de7-5fff-4805-8b30-9ab95493317d/",
        "recommends": [],
        "release": "2",
        "requires": [],
        "rpm_buildhost": "smqe-ws15",
        "rpm_group": "Internet/Applications",
        "rpm_header_end": 2329,
        "rpm_header_start": 928,
        "rpm_license": "GPLv2",
        "rpm_packager": "",
        "rpm_sourcerpm": "fox-1.1-2.src.rpm",
        "rpm_vendor": "",
        "size_archive": 292,
        "size_installed": 42,
        "size_package": 2473,
        "suggests": [],
        "summary": "A dummy package of fox",
        "supplements": [],
        "time_build": 1331831360,
        "time_file": 1574862495,
        "url": "http://tstrachota.fedorapeople.org",
        "version": "1.1"
    }


Add content to repository ``foo``
*********************************

.. note::

   It is recommended to omit the ``relative_path`` and have Pulp generate a common pool location.
   This will be ``/repo/Packages/s/squirrel-0.1-1.noarch.rpm`` as shown below.

   When specifying a ``relative_path``, make sure to add the exact name of the package
   including its name, version, release and arch as in ``squirrel-0.1-1.noarch.rpm``.
   It is composed of the ``name-version-release.arch.rpm``.

   .. code-block:: none

      relative_path="squirrel-0.1-1.noarch.rpm"

Using pulp-cli commands :

.. literalinclude:: ../_scripts/add_remove_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/add_remove.sh
   :language: bash

Repository Version GET response (after task complete):

.. code:: json

    {
        "base_version": null,
        "content_summary": {
            "added": {
                "rpm.package": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/805de89c-1b1d-432c-993e-3eb9a3fedd22/versions/1/"
                }
            },
            "present": {
                "rpm.package": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version=/pulp/api/v3/repositories/rpm/rpm/805de89c-1b1d-432c-993e-3eb9a3fedd22/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1,
        "pulp_created": "2019-11-27T13:48:18.326333Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/805de89c-1b1d-432c-993e-3eb9a3fedd22/versions/1/"
    }

One-shot Upload
---------------

.. _advisory-upload-workflow:

Advisory upload
***************

Advisory upload requires a file or an artifact containing advisory information in the JSON format.
Repository is an optional argument to create new repository version with uploaded advisory.

Using pulp-cli commands :

.. literalinclude:: ../_scripts/advisory_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/advisory.sh
   :language: bash

Advisory GET response (after task complete):

.. code:: json

    {
        "artifact": "/pulp/api/v3/artifacts/b4e3a95c-eb82-410e-8f90-aba59d573058/",
        "description": "",
        "fromstr": "nobody@redhat.com",
        "id": "RHSA-XXXX:XXXX",
        "issued_date": "2014-09-24 00:00:00",
        "pkglist": [],
        "pulp_created": "2019-11-27T13:48:20.364919Z",
        "pulp_href": "/pulp/api/v3/content/rpm/advisories/51169df4-f7c6-46df-953c-1714e5dd5869/",
        "pushcount": "",
        "reboot_suggested": false,
        "references": [],
        "release": "",
        "rights": "",
        "severity": "",
        "solution": "",
        "status": "",
        "summary": "",
        "title": "",
        "type": "",
        "updated_date": "",
        "version": ""
    }

