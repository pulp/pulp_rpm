.. _sync-publish-workflow:

Create, Sync and Publish a Repository
=====================================

One of the most common workflows is a fetching content from a remote source and making it
available for users.

Create an RPM repository ``foo``
--------------------------------

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET response:

.. code:: json

    {
        "description": null,
        "latest_version_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/0/",
        "name": "foo",
        "pulp_created": "2019-11-27T13:30:28.159167Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/",
        "versions_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/"
    }

RPM Repositories support several additional options.

- metadata_signing_service:
    See :ref:`metadata_signing`.
- retain_package_versions:
    The maximum number of versions of each package to keep; as new versions of packages are added by upload, sync, or copy, older versions of the same packages are automatically removed. A value of 0 means "unlimited".

.. _create-remote:

Create a new remote ``bar``
---------------------------

By default ``policy='immediate`` which means that all the content is downloaded right away.
Specify ``policy='on_demand'`` to make synchronization of a repository faster and only
to download RPMs whenever they are requested by clients.

Also, you can specify ``client_cert`` and ``client_key`` if your remote require authorization with a certificate.

.. code:: shell

    http --form POST $BASE_ADDR/pulp/api/v3/remotes/rpm/rpm/ \
        name='bar' \
        url="$URL" \
        policy='on_demand' \
        client_cert=@./certificate.crt \
        client_key=@./certificate.key \
        tls_validation=False

If you want to use TLS validation you have to provide ``ca_cert`` too.

.. literalinclude:: ../_scripts/remote.sh
   :language: bash

Remote GET response:

.. code:: json

    {
        "ca_cert": null,
        "client_cert": null,
        "client_key": null,
        "download_concurrency": 20,
        "name": "bar",
        "policy": "on_demand",
        "proxy_url": null,
        "pulp_created": "2019-11-27T13:30:29.199173Z",
        "pulp_href": "/pulp/api/v3/remotes/rpm/rpm/2ceb5262-a5b2-4297-afdf-a31f7e46dfc5/",
        "pulp_last_updated": "2019-11-27T13:30:29.199187Z",
        "tls_validation": true,
        "url": "https://fixtures.pulpproject.org/rpm-unsigned/"
    }


.. note::

   While creating a new remote, you may set the field ``url`` to point to a mirror list feed. Pulp
   fetches the list of available mirrors and tries to download content from the first valid mirror.
   This means that whenever an error occurs during the synchronization, the whole sync process ends
   with an error too.

.. _versioned-repo-created:

Configuration for SLES 12+ repository with authentication
*********************************************************

If you would like to sync SLES 12+ repository you will need to specify an authentication as ``sles_auth_token``.

You can receive your token with script like this:

.. code:: bash

    curl -H "Authorization: Token token=YourOrganizationRegistrationCode" \
    https://scc.suse.com/connect/subscriptions/products | \
    tr "," "\n" | \
    grep -i "url" | \
    grep -i "SLE-SERVER"

Assuming your token is ``YourRepositoryToken``, create the remote with the ``sles_auth_token`` specified.

.. code:: bash

    http POST :/pulp/api/v3/remotes/rpm/rpm/ \
    name='SLESrepo' \
    url='https://updates.suse.com/SUSE/Updates/SLE-SERVER/12/x86_64/update/' \
    policy='on_demand' \
    sles_auth_token='YourRepositoryToken'

Sync repository ``foo`` using remote ``bar``
--------------------------------------------

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

You can specify ``mirror=True`` for a mirror mode. It means Pulp won't update
repository using previous repository version but create a new copy of remote
repository as a new repository version.

Optionally, you can skip ``SRPM`` packages by using ``skip_types:="[\"srpm\"]"``
option.

By default, ``optimize=True`` and sync will only proceed if changes are present.
You can override this by setting ``optimize=False`` which will disable optimizations and
run a full sync.

RepositoryVersion GET response (when sync task complete):

.. code:: json

    {
        "base_version": null,
        "content_summary": {
            "added": {
                "rpm.advisory": {
                    "count": 4,
                    "href": "/pulp/api/v3/content/rpm/advisories/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.package": {
                    "count": 35,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagecategory": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagecategories/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagegroup": {
                    "count": 2,
                    "href": "/pulp/api/v3/content/rpm/packagegroups/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagelangpacks": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagelangpacks/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                }
            },
            "present": {
                "rpm.advisory": {
                    "count": 4,
                    "href": "/pulp/api/v3/content/rpm/advisories/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.package": {
                    "count": 35,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagecategory": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagecategories/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagegroup": {
                    "count": 2,
                    "href": "/pulp/api/v3/content/rpm/packagegroups/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagelangpacks": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagelangpacks/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1,
        "pulp_created": "2019-11-27T13:30:31.961788Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
    }


.. _publication-workflow:

Create a Publication
--------------------

A publication can only be created once a sync task completes. You can specify checksum algorithm with the following optional parameters:

- metadata_checksum_type: affects all the repodata, including primary.xml, repomd.xml, etc.
  If not specified, the default SHA256 algorithm will be used.

- package_checksum_type: affects package checksum type in all repo metadata files.
  If not specified, the default SHA256 algorithm will be used.
  Because of on_demand sync, it is possible that the requested checksum is not available.
  In such case the one from the remote repo will be used.

.. literalinclude:: ../_scripts/publication.sh
   :language: bash

Publication GET response (when task complete):

.. code:: json

    {
        "publisher": null,
        "pulp_created": "2019-11-27T13:30:36.006972Z",
        "pulp_href": "/pulp/api/v3/publications/rpm/rpm/c90316fc-bf2a-458a-93b8-d3d75614572f/",
        "repository": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/",
        "repository_version": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
    }

The GPG signature check options are configurable from this REST API endpoint as well. This can be
done via the following options:

- gpgcheck: perform a GPG signature check on the packages retrieved from this repository.

- repo_gpgcheck: perform a GPG signature check on the repodata.

Additionally, an option is provided to let the user decide whether or not to generate sqlite metadata
(defaults to 'false'). Sqlite metadata not commonly used.

- sqlite_metadata: generate sqlite metadata in addition to standard XML metadata

We encourage users to take a look at the `pulp_rpm API documentation <../restapi.html#operation/publications_rpm_rpm_create>`_
to see the default values for these options.


Create a Distribution for the Publication
-----------------------------------------

.. literalinclude:: ../_scripts/distribution.sh
   :language: bash

Distribution GET response (when task complete):

.. code:: json

    {
        "base_path": "foo",
        "base_url": "http://pulp3-source-fedora30.pavels-macbook-pro.example.com/pulp/content/foo",
        "content_guard": null,
        "name": "baz",
        "publication": "/pulp/api/v3/publications/rpm/rpm/c90316fc-bf2a-458a-93b8-d3d75614572f/",
        "pulp_created": "2019-11-27T13:30:38.238857Z",
        "pulp_href": "/pulp/api/v3/distributions/rpm/rpm/c1166d2d-0832-4e90-85fd-e34e94e6a156/"
    }

