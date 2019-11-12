Copy RPM content between repositories
=====================================

If you want to copy RPM content from one repository into another repository, you can do so.


.. _copy-workflow:

Copy workflow
-------------

You can use the modify endpoint on a repository to copy all content present in one repository
version to another by specifying a base version.

``http POST http://localhost:24817${REPO_HREF}modify/ base_version=${BASE_REPO_HREF}``

.. code:: json

    {
        "created_resources": [
            "/pulp/api/v3/repositories/rpm/rpm/5fc8a78e-068a-47c0-b728-a5475042573a/versions/2/"
        ],
    }
