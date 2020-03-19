Client Bindings
===============

Python Client
-------------

The `pulp-rpm-client package <https://pypi.org/project/pulp-rpm-client/>`_ on PyPI provides
bindings for all API calls in the `pulp_rpm API documentation <../restapi.html>`_. It is
currently published daily and with every RC.

The `pulpcore-client package <https://pypi.org/project/pulpcore-client/>`_ on PyPI provides bindings
for all API calls in the `pulpcore API documentation <https://docs.pulpproject.org/en/3.0/nightly/
restapi.html>`_. It is currently published daily and with every RC.


Ruby Client
-----------

The `pulp_rpm_client Ruby Gem <https://rubygems.org/gems/pulp_rpm_client>`_ on rubygems.org
provides bindings for all API calls in the `pulp_rpm API documentation <../restapi.html>`_. It
is currently published daily and with every RC.

The `pulpcore_client Ruby Gem <https://rubygems.org/gems/pulpcore_client>`_ on rubygems.org provides
bindings for all API calls in the `pulpcore API documentation <https://docs.pulpproject.org/en/3.0/
nightly/restapi.html>`_. It is currently published daily and with every RC.


Client in a language of your choice
-----------------------------------

A client can be generated using Pulp's OpenAPI schema and any of the available `generators
<https://openapi-generator.tech/docs/generators.html>`_.

Generating a client is a two step process:

**1) Download the OpenAPI schema for pulpcore and all installed plugins:**

.. code-block:: bash

    curl -o api.json http://<pulp-hostname>:24817/pulp/api/v3/docs/api.json

The OpenAPI schema for a specific plugin can be downloaded by specifying the plugin's module name
as a GET parameter. For example for ``pulp_rpm`` only endpoints use a query like this:

.. code-block:: bash

    curl -o api.json http://<pulp-hostname>:24817/pulp/api/v3/docs/api.json?plugin=pulp_rpm

**2) Generate a client using openapi-generator.**

The schema can then be used as input to the openapi-generator-cli. The documentation on getting
started with openapi-generator-cli is available on
`openapi-generator.tech <https://openapi-generator.tech/#try>`_.


Generating a client for a dev environment
-----------------------------------------

The pulp dev environment provided by `ansible-pulp <https://github.com/pulp/ansible-pulp>`_
introduces a set of useful
`aliases <https://github.com/pulp/ansible-pulp/tree/master/roles/pulp-devel#aliases>`_,
such as `pbindings`.

Examples:

- generating python bindings for pulp_rpm:

.. code-block:: bash

    pbindings pulp_rpm python

- generating ruby bindings for pulp_rpm with '3.0.0rc1.dev.10' version

.. code-block:: bash

    pbindings pulp_rpm ruby 3.0.0rc1.dev.10
