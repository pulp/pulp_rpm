======================
ISO Export Distributor
======================

The ISO Export Distributor can be used to build an ISO image out of the content available in RPM repositories.
The ISO Export Distributor id is ``export_distributor``.


Configuration Parameters
========================

The following options are available to the yum distributor configuration.
In the event a repository does not have a feed, the relative path is also
required. If a feed is specified,the relative path will be derived from it
unless otherwise overridden.

["http_publish_dir", "start_date", "end_date", "iso_prefix"]

Required Configuration Parameters
---------------------------------

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

Optional Configuration Parameters
---------------------------------

``https_ca``
 CA certificate used to sign the SSL certificate the server is using to host
 this repository. This certificate will be made available to bound consumers so
 they can verify the server's identity. The value to this option must be the
 full path to the certificate.

``https_publish_dir``
 Override the HTTP_PUBLISH_DIR, where the ISO will be stored after generation. This is mainly used for unit
 tests.

``skip``
 List of content types to skip during the creation of the ISO.
 If unspecified, all types will be published. Valid values are: rpm, drpm,
 distribution, errata, packagegroup.
