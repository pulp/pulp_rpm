Copy RPM content between repositories
=====================================

If you want to copy RPM content from one repository into another repository, you can do so.


.. _copy-workflow:

Copy workflow
-------------

You can use the modify endpoint on a repository to copy all content present in one repository
version to another by specifying a base version.

.. literalinclude:: ../_scripts/copy.sh
   :language: bash

Repository Version GET response (after task complete):

.. code:: json

    {
        "base_version": "/pulp/api/v3/repositories/rpm/rpm/c8c632eb-cf9a-494f-8e12-b3e651b6e75e/versions/1/",
        "content_summary": {
            "added": {},
            "present": {
                "rpm.package": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version=/pulp/api/v3/repositories/rpm/rpm/c8c632eb-cf9a-494f-8e12-b3e651b6e75e/versions/3/"
                }
            },
            "removed": {
                "rpm.advisory": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/advisories/?repository_version_removed=/pulp/api/v3/repositories/rpm/rpm/c8c632eb-cf9a-494f-8e12-b3e651b6e75e/versions/3/"
                }
            }
        },
        "number": 3,
        "pulp_created": "2019-11-27T16:07:21.561748Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/c8c632eb-cf9a-494f-8e12-b3e651b6e75e/versions/3/"
    }

