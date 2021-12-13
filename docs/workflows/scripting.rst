Scripting
=========

Each workflow renders bash scripts that allow the developers to ensure the continued correctness of
the instructions. These scripts may also be helpful to users as a basis for their own scripts. All
of the scripts can be found at https://github.com/pulp/pulp_rpm/tree/main/docs/_scripts/

Some scripts have conditional statements for setting REPO_NAME, REMOTE_NAME, and DIST_NAME.
These are used by Pulp team for validity testing.

The scripts come in pairs, with one (`scriptname_cli.sh`) using pulp-cli commands where available, and the other
(`scriptname.sh`) using httpie REST calls.

The following scripts are used in conjunction with all the workflow scripts:

**Base**

Setting up to use pulp-cli:

.. literalinclude:: ../_scripts/base_cli.sh
   :language: bash

Setting up to use httpie:

.. literalinclude:: ../_scripts/base.sh
   :language: bash

Correctness Checks
------------------

.. warning::

    These scripts can harm your data.

To check the correctness of the sync with publish and download workflow scripts, they can all be run together using:

Using pulp-cli commands :

.. literalinclude:: ../_scripts/docs_check_sync_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/docs_check_sync.sh
   :language: bash

To check the correctness of the upload with publish and download workflow scripts, they can all be run together using:

Using pulp-cli commands :

.. literalinclude:: ../_scripts/docs_check_upload_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/docs_check_upload.sh
   :language: bash

To check the correctness of the basic copy with publish and download workflow scripts, they can all be run together using:

Using pulp-cli commands :

.. literalinclude:: ../_scripts/docs_check_copy_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/docs_check_copy.sh
   :language: bash
