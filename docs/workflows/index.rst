All the examples below come in two forms. One uses the `pulp-cli <https://github.com/pulp/pulp-cli>`__
project, and the other uses the `httpie <https://httpie.org/doc>`__ application to talk directly to the REST API.

The pulp-cli command examples assume that the user executing the commands has configured ``pulp-cli`` as with the following command::

    pulp config create \
      --username admin \
      --password YOUR-ADMIN-PASSWORD-HERE \
      --base-url http://localhost:24817 \
      --no-verify-ssl


REST API examples using `httpie <https://httpie.org/doc>`__ commands assume that the user executing the commands
has a ``.netrc`` file in their home directory. The ``.netrc`` should have the following configuration::

    machine localhost
    login admin
    password password

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
``httpie`` documentation on how to do that.

.. note::

    ``pulp-cli`` is under active development, and does not yet have 100% coverage of the REST API. As a result, some
    examples rely on ``httpie`` even in the ``pulp-cli`` code sections.

The examples also make use of ``curl`` and the `jq library <https://stedolan.github.io/jq/>`_
to parse the json received from requests, in order to get the unique urls generated
when objects are created. To follow this documentation as-is please install the jq
library with:

``$ sudo dnf install jq curl``

Workflows
---------

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
