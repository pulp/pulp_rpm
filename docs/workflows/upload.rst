Upload and Manage Content
=========================

Content can be added to a repository not only by synchronizing from a remote source but also by
 uploading.


Upload ``foo.rpm``
------------------

Create an Artifact by uploading the file to Pulp.

``$ http --form POST http://localhost:8000/pulp/api/v3/artifacts/ file@./foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "_href": "/pulp/api/v3/artifacts/1/",
        ...
    }

Create ``rpm`` content from an Artifact
---------------------------------------

Create a content unit and point it to your artifact

``$ http POST http://localhost:8000/pulp/api/v3/content/rpm/packages/ relative_path=foo.rpm artifact="/pulp/api/v3/artifacts/1/" filename=foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "_href": "/pulp/api/v3/content/rpm/packages/36/",
        "artifact": "/pulp/api/v3/artifacts/1/",
        "relative_path": "foo.rpm",
        "type": "rpm"
    }

``$ export CONTENT_HREF=$(http :8000/pulp/api/v3/content/rpm/packages/ | jq -r '.results[] | select( .relative_path == "foo.rpm") | ._href')``


Add content to repository ``foo``
---------------------------------

``$ http POST :8000${REPO_HREF}versions/ add_content_units:="[\"$CONTENT_HREF\"]"``

