Upload and Manage Content
=========================

Content can be added to a repository not only by synchronizing from a remote source but also by
uploading.


.. _upload-workflow:

Upload ``foo.rpm``
------------------

Create an Artifact by uploading the file to Pulp.

``$ http --form POST http://localhost:24817/pulp/api/v3/artifacts/ file@./foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "pulp_href": "/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/",
    }

Create ``rpm`` content from an Artifact
---------------------------------------

Create a content unit and point it to your artifact

``$ http POST http://localhost:24817/pulp/api/v3/content/rpm/packages/ artifact="/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/" relative_path=foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "pulp_href": "/pulp/api/v3/content/rpm/packages/2df123b2-0d38-4a43-9b21-a3e830ea1324/",
        "artifact": "/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/",
    }

``$ export CONTENT_HREF=$(http :24817/pulp/api/v3/content/rpm/packages/ | jq -r '.results[] | select( .location_href == "foo-4.1-1.noarch.rpm") | .pulp_href')``


Add content to repository ``foo``
---------------------------------

``$ http POST :24817${REPO_HREF}modify/ add_content_units:="[\"$CONTENT_HREF\"]"``


.. _one-shot-upload-workflow:

One shot upload
---------------

You can use one shot uploader to upload one rpm and optionally create new repository version with rpm you uploaded.
With this call you can substitute previous two (or three) steps (create artifact, content from artifact and optionally add content to repo).

``http --form POST http://localhost:24817/pulp/api/v3/rpm/upload/ file@./foo-1.0-1.noarch.rpm repository=${REPO_HREF}``

.. code:: json

    {
       "pulp_href": "/pulp/api/v3/tasks/f2b525e3-8d8f-4246-adab-2fabd2b089a8/",
       "created_resources": [
           "/pulp/api/v3/content/rpm/packages/1edf8d4e-4293-4b66-93cd-8e913731c87a/",
           "/pulp/api/v3/repositories/rpm/rpm/64bdeb44-c6d3-4ed7-9c5a-94b264a6b7b5/versions/2/"
       ],
    }

