Create, Sync and Publish a Repository
=====================================

One of the most common workflows is a fetching content from a remote source and making it
available for users.

Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/pulp/api/v3/repositories/ name=foo``

.. code:: json

    {
        "_href": "/pulp/api/v3/repositories/1/",
        ...
    }

``$ export REPO_HREF=$(http :8000/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')``

Create a new remote ``bar``
---------------------------

``$ http POST http://localhost:8000/pulp/api/v3/remotes/rpm/rpm/ name='bar' url='https://repos.fedorapeople.org/pulp/pulp/fixtures/rpm-unsigned/' policy='on_demand'``

.. code:: json

    {
        "_href": "/pulp/api/v3/remotes/rpm/rpm/1/",
        ...
    }

``$ export REMOTE_HREF=$(http :8000/pulp/api/v3/remotes/rpm/rpm/ | jq -r '.results[] | select(.name == "bar") | ._href')``

Sync repository ``foo`` using remote ``bar``
--------------------------------------------

``$ http POST :8000${REMOTE_HREF}sync/ repository=$REPO_HREF``

Look at the new Repository Version created
------------------------------------------

``$ http GET :8000${REPO_HREF}versions/1/``

.. code:: json

    {
        "_added_href": "/pulp/api/v3/repositories/1/versions/1/added_content/",
        "_content_href": "/pulp/api/v3/repositories/1/versions/1/content/",
        "_href": "/pulp/api/v3/repositories/1/versions/1/",
        "_removed_href": "/pulp/api/v3/repositories/1/versions/1/removed_content/",
        "content_summary": {
            "package": 35,
            "update": 4
        },
        "created": "2018-02-23T20:29:54.499055Z",
        "number": 1
    }


Create a ``rpm`` Publisher
--------------------------

``$ http POST http://localhost:8000/pulp/api/v3/publishers/rpm/rpm/ name=bar``

.. code:: json

    {
        "_href": "/pulp/api/v3/publishers/rpm/rpm/1/",
        ...
    }

``$ export PUBLISHER_HREF=$(http :8000/pulp/api/v3/publishers/rpm/rpm/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Create a Publication using publisher `bar`
------------------------------------------

``$ http POST :8000${PUBLISHER_HREF}publish/ repository=$REPO_HREF``

.. code:: json

    [
        {
            "_href": "/pulp/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
            "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
        }
    ]

``$ export PUBLICATION_HREF=$(http :8000/pulp/api/v3/publications/ | jq -r --arg PUBLISHER_HREF "$PUBLISHER_HREF" '.results[] | select(.publisher==$PUBLISHER_HREF) | ._href')``

Create a Distribution for the Publication
-----------------------------------------

``$ http POST http://localhost:8000/pulp/api/v3/distributions/ name='baz' base_path='foo' publication=$PUBLICATION_HREF``


.. code:: json

    {
        "_href": "/pulp/api/v3/distributions/1/",
       ...
    }

