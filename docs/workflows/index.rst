Workflows
=========

All REST API examples below use `httpie <https://httpie.org/doc>`__ to perform the requests.
The ``httpie`` commands below assume that the user executing the commands has a ``.netrc`` file
in the home directory. The ``.netrc`` should have the following configuration::

    machine localhost
    login admin
    password password

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
``httpie`` documentation on how to do that.

This documentation makes use of the curl and `jq library <https://stedolan.github.io/jq/>`_
to parse the json received from requests, in order to get the unique urls generated
when objects are created. To follow this documentation as-is please install the jq
library with:

``$ sudo dnf install jq curl``


.. toctree::
   :maxdepth: 2

   scripting
   create_sync_publish
   upload
   use_pulp_repo
   manage
   copy
   metadata_signing
   alternate-content-source
