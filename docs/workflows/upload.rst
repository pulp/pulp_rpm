Upload Content
==============

.. _upload-workflow:

Content can be added to a repository not only by synchronizing from a remote source but also by
uploading.

Bulk Upload
-----------

Upload artifacts
****************

Create an Artifact by uploading the file to Pulp. In this instance, we will upload
``foo-4.1-1.noarch.rpm``.

``$ http --form POST http://localhost:24817/pulp/api/v3/artifacts/ file@./foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "pulp_href": "/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/",
    }

Create content from artifacts
*****************************

Create a content unit and point it to your artifact

``$ http POST http://localhost:24817/pulp/api/v3/content/rpm/packages/ artifact="/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/" relative_path=foo-4.1-1.noarch.rpm``

.. code:: json

    {
        "pulp_href": "/pulp/api/v3/content/rpm/packages/2df123b2-0d38-4a43-9b21-a3e830ea1324/",
        "artifact": "/pulp/api/v3/artifacts/d1dd56aa-c236-414a-894f-b3d9334d2e73/",
    }

``$ export CONTENT_HREF=$(http :24817/pulp/api/v3/content/rpm/packages/ | jq -r '.results[] | select( .location_href == "foo-4.1-1.noarch.rpm") | .pulp_href')``


Add content to repository ``foo``
*********************************

``$ http POST :24817${REPO_HREF}modify/ add_content_units:="[\"$CONTENT_HREF\"]"``


One-shot Upload
---------------

.. _advisory-upload-workflow:

Advisory upload
***************

Advisory upload requires a file or an artifact containing advisory information in the JSON format.
Repository is an optional argument to create new repository version with uploaded advisory.

``http --form POST :24817/pulp/api/v3/content/rpm/advisories/ file@./advisory.json relative_path="advisory.json" repository="/pulp/api/v3/repositories/1b9ffafc-8a5a-4e06-9f31-6de1d1632c4c/"``
