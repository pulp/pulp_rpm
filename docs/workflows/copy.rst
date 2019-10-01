Copy RPM content between repositories
=====================================

If you want to copy RPM content from one repository into another repository, you can do so.


.. _copy-workflow:

Copy workflow
-------------

You can use the copy endpoint to copy RPM-related content present in one repository or
repository version over to another repository. If you specify a repository, then the latest
repository version for that repository will be used.

``http POST http://localhost:24817/pulp/api/v3/rpm/copy/ source_repo=${SRC_REPO_HREF} dest_repo=${DEST_REPO_HREF}``

or

``http POST http://localhost:24817/pulp/api/v3/rpm/copy/ source_repo_version=${SRC_REPO_VER_HREF} dest_repo=${DEST_REPO_HREF}``

.. code:: json

    {
       "_href": "/pulp/api/v3/tasks/f2b525e3-8d8f-4246-adab-2fabd2b089a8/",
       "created_resources": [
           "/pulp/api/v3/content/rpm/packages/1edf8d4e-4293-4b66-93cd-8e913731c87a/",
       ],
    }

You can also specify which types of content you would like to copy by providing a value for the
"types" parameter. Types that are not listed will not be copied. The supported types are "package"
and "advisory". For example, this query will copy only advisories, and not packages. If not
provided, all types will be copied.

``http POST http://localhost:24817/pulp/api/v3/rpm/copy/ source_repo=${SRC_REPO_HREF} dest_repo=${DEST_REPO_HREF} types=advisory``
