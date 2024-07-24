# Client Bindings

## Python Client

The [pulp-rpm-client package](https://pypi.org/project/pulp-rpm-client/) on PyPI provides
bindings for all API calls in the [pulp_rpm API documentation](site:pulp_rpm/restapi/). It is
currently published daily and with every RC.

The [pulpcore-client package](https://pypi.org/project/pulpcore-client/) on PyPI provides bindings
for all API calls in the [pulpcore API documentation](site:pulpcore/restapi/).
It is currently published daily and with every RC.

## Ruby Client

The [pulp_rpm_client Ruby Gem](https://rubygems.org/gems/pulp_rpm_client) on rubygems.org
provides bindings for all API calls in the [pulp_rpm API documentation](site:pulp_rpm/restapi/). It
is currently published daily and with every RC.

The [pulpcore_client Ruby Gem](https://rubygems.org/gems/pulpcore_client) on rubygems.org provides
bindings for all API calls in the [pulpcore API documentation](site:pulpcore/restapi/). It is currently published daily and with every RC.

## Client in a language of your choice

A client can be generated using Pulp's OpenAPI schema and any of the available [generators](https://openapi-generator.tech/docs/generators.html).

Generating a client is a two step process:

**1) Download the OpenAPI schema for pulpcore and all installed plugins:**

```bash
curl -o api.json http://<pulp-hostname>:24817/pulp/api/v3/docs/api.json
```

The OpenAPI schema for a specific plugin can be downloaded by specifying the plugin's module name
as a GET parameter. For example for `pulp_rpm` only endpoints use a query like this:

```bash
curl -o api.json http://<pulp-hostname>:24817/pulp/api/v3/docs/api.json?plugin=pulp_rpm
```

**2) Generate a client using openapi-generator.**

The schema can then be used as input to the openapi-generator-cli. The documentation on getting
started with openapi-generator-cli is available on
[openapi-generator.tech](https://openapi-generator.tech/#try).

## Generating a client for a dev environment

The pulp dev environment provided by [pulp_installer](https://github.com/pulp/pulp_installer)
introduces a set of useful
[aliases](https://github.com/pulp/pulp_installer/tree/main/roles/pulp-devel#aliases),
such as `pbindings`.

Examples:

- generating python bindings for pulp_rpm:

```bash
pbindings pulp_rpm python
```

- generating ruby bindings for pulp_rpm with '3.0.0rc1.dev.10' version

```bash
pbindings pulp_rpm ruby 3.0.0rc1.dev.10
```
