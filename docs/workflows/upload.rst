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
        "_href": "/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/",
    }

Create ``rpm`` content from an Artifact
---------------------------------------

Create a content unit and point it to your artifact

``$ http POST http://localhost:24817/pulp/api/v3/content/rpm/packages/ artifact="/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/" relative_path=foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "_href": "/pulp/api/v3/content/rpm/packages/2df123b2-0d38-4a43-9b21-a3e830ea1324/",
        "artifact": "/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/",
    }

``$ export CONTENT_HREF=$(http :24817/pulp/api/v3/content/rpm/packages/ | jq -r '.results[] | select( .location_href == "foo-4.1-1.noarch.rpm") | ._href')``


Add content to repository ``foo``
---------------------------------

``$ http POST :24817${REPO_HREF}versions/ add_content_units:="[\"$CONTENT_HREF\"]"``


.. _one-shot-upload-workflow:

One shot upload
---------------

You can use one shot uploader to upload one rpm and optionally create new repository version with rpm you uploaded.
With this call you can substitute previous two (or three) steps (create artifact, content from artifact and optionally add content to repo).

``http --form POST http://localhost:24817/pulp/api/v3/rpm/upload/ file@./foo-1.0-1.noarch.rpm repository=${REPO_HREF}``

.. code:: json

    {
       "_href": "/pulp/api/v3/tasks/f2b525e3-8d8f-4246-adab-2fabd2b089a8/",
       "created_resources": [
           "/pulp/api/v3/content/rpm/packages/1edf8d4e-4293-4b66-93cd-8e913731c87a/",
           "/pulp/api/v3/repositories/64bdeb44-c6d3-4ed7-9c5a-94b264a6b7b5/versions/2/"
       ],
    }

.. _modular_content_upload_workflow:

Upload modular content
----------------------

You can upload modulemd and modulemd-defaults content (with one file) and optionally create new
repository version with modulemds and modulemd-defaults you uploaded.
If there is no new modulemd or modulemd-defaults within upload new repository version is not created.

You can use file for upload
``http --form POST :24817/pulp/api/v3/modularity/upload/ file@./modules.yaml repository=${REPO_HREF}``

or you can use already uploaded artifact
``http --form POST :24817/pulp/api/v3/modularity/upload/ artifact="/pulp/api/v3/artifacts/27e4527e-8ee0-41ee-a0c9-555fe78832b9/" repository=${REPO_HREF}``

.. code:: json

    {
        "_href": "/pulp/api/v3/tasks/aa74fcfa-1483-4963-8b49-07b04f11ac01/",
        "created_resources": [
            "/pulp/api/v3/modulemd/rpm/modulemd/428edea5-95be-4bf1-8f42-5eeb018e3f13/",
            "/pulp/api/v3/artifacts/66e1fa94-5c0c-44b5-9175-ec405520fa08/",
            "/pulp/api/v3/modulemd/rpm/modulemd/506fe9fd-75e3-43e9-b5e1-b4bc112f15a4/",
            "/pulp/api/v3/artifacts/adb7a3f6-2752-4379-b619-952edc114b4d/",
            "/pulp/api/v3/modulemd-defaults/rpm/modulemd-defaults/f5e11930-bab3-4c06-bc39-c18361838d61/",
            "/pulp/api/v3/modulemd-defaults/rpm/modulemd-defaults/58edcaf4-503a-4b30-b302-fb9b7147959d/",
            "/pulp/api/v3/artifacts/72c9c491-f3f0-4db4-a36a-073a9e58cd18/",
            "/pulp/api/v3/repositories/741a0c9e-fca9-46b6-911f-548b2a33ea51/versions/1/"
        ],
        "state": "completed",
    }
