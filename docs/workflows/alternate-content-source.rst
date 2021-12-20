Alternate Content Sources
=========================

Alternate Content Sources (ACS) can help speed up populating of new repositories.
If you have content stored locally or geographically near you which matches
the remote content, Alternate Content Sources will allow you to substitute
this content, allowing for faster data transfer.

`Alternate Content Sources <https://docs.pulpproject.org/pulpcore/workflows/alternate-content-sources.html>`_
base is provided by pulpcore plugin.

To use an Alternate Content Source you need a ``RPMRemote`` with path of your ACS.

.. warning::

    Remotes with mirrorlist URLs cannot be used as an Alternative Content Source.

.. code-block:: bash

    http POST $BASE_ADDR/pulp/api/v3/remotes/rpm/rpm/ name="myRemoteAcs" policy="on_demand" url="http://fixtures.pulpproject.org/rpm-unsigned/"

Create Alternate Content Source
-------------------------------

Create an Alternate Content Source.

.. code-block:: bash

    http POST $BASE_ADDR/pulp/api/v3/acs/rpm/rpm/ name="myAcs" remote=$REMOTE_HREF

Alternate Content Source Paths
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have more places with ACS within one base path you can specify them
by paths and all of them will be considered as a ACS.

.. code-block:: bash

    http POST $BASE_ADDR/pulp/api/v3/remotes/rpm/rpm/ name="myRemoteACS" policy="on_demand" url="http://fixtures.pulpproject.org/"
    http POST $BASE_ADDR/pulp/api/v3/acs/file/file/ name="myAcs" remote=$REMOTE_HREF paths:='["rpm-unsigned/", "rpm-distribution-tree/"]'

Refresh Alternate Content Source
--------------------------------

To make your ACS available for future syncs you need to call ``refresh`` endpoint
on your ACS. This create a catalogue of available content which will be used instead
new content if found.

.. code-block:: bash

    http POST $BASE_ADDR/pulp/api/v3/acs/rpm/rpm/<ACS-UUID>/refresh/

Alternate Content Source has a global scope so if any content is found in ACS it
will be used in all future syncs.
