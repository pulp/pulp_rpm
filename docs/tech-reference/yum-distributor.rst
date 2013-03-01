The Yum Distributor id is ``yum_distributor``.

Yum Distributor Configuration options
=====================================

The following options are available to the yum distributor configuration.
In the event a repository does not have a feed, the relative path is also
required. If a feed is specified,the relative path will be derived from it
unless otherwise overridden.

``relative_url``
 Relative path at which the repository will be served. If this is not specified,
 the relative path is derived from the ``feed_url`` option. For example:
 ``relative_url="rhel_6.2" may translate to publishing at http://localhost/pulp/repos/rhel_6.2``

``http``
 Flag indicating if the repository will be served over a non-SSL connection.
 Valid values to this option are ``True`` and ``False``. This option is
 required.

``https``
 Flag indicating if the repository will be served over an SSL connection. If
 this is set to true, the ``https_ca`` option should also be specified to ensure
 consumers bound to this repository have the necessary certificate to validate
 the SSL connection. Valid values to this option are ``True`` and ``False``.
 This option is required.

``protected``
 Protect the published repository with repo authentication. Valid values to this
 option are ``True`` and ``False``.

``auth_cert``
 Certificate that will be provided to consumers bound to this repository. This
 certificate should contain entitlement information to grant access to this
 repository, assuming the repository is protected. The value to this option must
 be the full path to the certificate file. The file must contain both
 the certificate itself and its private key.

``auth_ca``
 CA certificate that was used to sign the certificate specified in ``auth-cert``.
 The server will use this CA to verify that the incoming request's client certificate
 is signed by the correct source and is not forged. The value to this option
 must be the full path to the CA certificate file.

``https_ca``
 CA certificate used to sign the SSL certificate the server is using to host
 this repository. This certificate will be made available to bound consumers so
 they can verify the server's identity. The value to this option must be the
 full path to the certificate.

``gpgkey``
 GPG key used to sign RPMs in this repository. This key will be made available
 to consumers to use in verifying content in the repository. The value to this
 option must be the full path to the GPG key file.

``use_createrepo``
 This is mostly a debug flag to override default snippet-based metadata generation.
 ``False`` will not run and uses existing metadata from sync.

``checksum_type``
 Checksum type to use for metadata generation

``skip``
 List of content types to skip during the repository publish.
 If unspecified, all types will be published. Valid values are: rpm, drpm,
 distribution, errata, packagegroup.
