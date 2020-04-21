Scripting
=========

Each workflow renders bash scripts that allow the developers to ensure the continued correctness of
the instructions. These scripts may also be helpful to users as a basis for their own scripts. All
of the scripts can be found at https://github.com/pulp/pulp_rpm/tree/master/docs/_scripts/

Some scripts have conditional statements for setting REPO_NAME.
These are used by Pulp team for validity testing.

The following scripts are used in conjunction with all the workflow scripts:

**Base**

.. literalinclude:: ../_scripts/base.sh
   :language: bash

Correctness Check
-----------------

.. warning::

    These scripts can harm your data.

To check the correctness of the sync with publish and download workflow scripts, they can all be run together using:

.. literalinclude:: ../_scripts/docs_check_sync.sh
   :language: bash

To check the correctness of the upload with publish and download workflow scripts, they can all be run together using:
script.

.. literalinclude:: ../_scripts/docs_check_upload.sh
   :language: bash