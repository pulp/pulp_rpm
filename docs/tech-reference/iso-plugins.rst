===========
ISO Plugins
===========

ISO Type
========

The ISO Plugins only have one type, the ISO. The ISO type's ID is ``iso``. The following is a descripton of the
ISO unit type that is used by the ISO plugins. The unit key is a combination of fields that can be used to
uniquely identify an ISO. ISOs have no additional metadata.

Unit Key
--------

The unit key for the ISO type is an ordered list of ``name``,  ``checksum``, and  ``size``. Each of
these attributes is described below.

``name``
 This is the filename of the ISO.

``checksum``
 This is the `SHA-256 <http://en.wikipedia.org/wiki/SHA-2>`_ checksum of the ISO file.

``size``
 This is the size in bytes of the ISO file.

Metadata
--------

ISOs have no additional metadata outside of the unit key.

ISO Importer
============

The ISO Importer can be used to sync an ISO repository with an upstream feed. The ISO Importer ID is
``iso_importer``.

An ISO repository is a fairly basic type of repository. It should be accessible via ``feed_url``, and there
should be a file named ``PULP_MANIFEST`` available by appending ``/PULP_MANIFEST`` to the ``feed_url``. For
example, if the ``feed_url`` is http://example.com/iso_repository, the ISO Importer will look for the manifest
at http://example.com/iso_repository/PULP_MANIFEST.

The manifest should be a CSV file with one row per ISO and these three columns, in order: name, checksum, and
size. The CSV file should not have a header row. The name should be the filenames of the ISO, and
the ISO should be accessible by appending the name to the ``feed_url``. The checksum should be the
SHA-256 checksum of the ISO, and the size column should represent the size of the ISO in bytes. Here is an
example ``PULP_MANIFEST`` file::

    example-1.0.iso,f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0,127346
    example-1.1.iso,c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16,564830

Configuration Parameters
------------------------

The following configuration parameters are all optional, and can be used to determine the behavior of the ISO
importer.

``feed_url``
 This should be a string that represents the URL to an upstream ISO repository that you would like this importer
 to be able to synchronize with. This parameter is optional because it is valid to create an ISO importer that
 does not synchronize with an upstream feed, but is rather used to contain uploaded ISOs, or ISOs that are
 copied from other repositories. This parameter becomes required if any of the other parameters are provided.

``max_speed``
 This should be a numerical value, or a string that can be interpreted as a numerical value, representing the
 maximum speed that the importer should be allowed to transfer ISOs at when synchronizing with ``feed_url``.
 It should be specified in units of bytes per second.

``num_threads``
 This should be an integer, or a string that can be interpreted as an integer, representing the maximum number
 of concurrent downloads that should be performed when synchronizing with ``feed_url``. This parameter defaults
 to 5.

``proxy_password``
 A string representing the password that should be used to authenticate with the proxy server specified in
 ``proxy_url``. This parameter is required if the ``proxy_username`` is provided.

``proxy_port``
 An integer, or a string that can be interpreted as an integer, representing the port that should be used when
 connecting to ``proxy_url``.

``proxy_url``
 A string representing the URL of the proxy server that should be used when synchronizing with ``feed_url``.
 This parameter is required if any of the other proxy setting are provided.

``proxy_user``
 A string representing the username that should be used to authenticate with the proxy server at ``proxy_url``.
 This parameter is required if the ``proxy_password`` is provided.

``remove_missing_units``
 This is a boolean value, or a string "True" or "False". If set to "True", the importer will remove any ISOs
 that are currently in the local Pulp repository that are not found in the manifest at ``feed_url``. If
 "False", missing ISOs will not be removed. This parameter defaults to False.

``ssl_ca_cert``
 This is a string representing the SSL certificate authority certificate that should be used to validate the
 server responding at ``feed_url``. It should be provided in PEM format.

``ssl_client_cert``
 This is a string representing the SSL client certificate that should be used to authenticate the importer to
 the upstream repository at ``feed_url``. It should be provided in PEM format. This parameter is required if the
 ``ssl_client_key`` is provided.

``ssl_client_key``
 This is a string representing the private key for ``ssl_client_cert``. It should be provided in PEM format.

``validate_downloads``
 This is a boolean value, or a string "True" or "False". If set to "True", the importer will check the
 downloaded ISOs' file sizes and checksums against the expected values in the manifest when downloading from
 ``feed_url``. If "False", no validation will be performed. This parameter defaults to True.

ISO Distributor
===============

The ISO Distributor can be used to publish available ISOs in an ISO repository over http or https. It is
distinct from the `export_distributor`. The ISO Distributor ID is ``iso_distributor``.

Configuration Parameters
------------------------

The following configuration parameters can be used to determine the behavior of the ISO Distributor. Both
configuration parameters are required.

``serve_http``
 This is a boolean value, or a string "True" or "False". If set to True, the distributor will publish the ISO
 repository over plain HTTP, port 80. If False, it will not be published over plain HTTP.

``serve_https``
 This is a boolean value, or a string "True" or "False". If set to True, the distributor will publish the ISO
 repository over SSL protected HTTP, port 443. If False, it will not be published over HTTPS.

``ssl_auth_ca_cert``
 If the distributor is configured with an authorization CA certificate and the repository protection WSGI app is
 enabled, the distributed repository will become a protected repository. The given CA certificate will be used
 to verify the clients' entitlement certificates. If this certificate is not provided, the repository will be an
 unprotected repository.
