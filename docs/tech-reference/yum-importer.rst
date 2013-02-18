Yum Importer Configuration options
==================================

The following options are available to the yum importer configuration. All
configuration values are optional.

``feed_url``
 URL where the repository's content will be synchronized from. This can be either
 an HTTP URL or a location on disk represented as a file URL.

``ssl_verify``
 Indicates if the server's SSL certificate is verified against the CA certificate
 uploaded. The certificate should be verified against the CA for each client request.
 Has no effect for non-SSL feeds. Valid values to this option are ``True`` and ``False``.

``ssl_ca_cert``
 CA certificate string used to validate the feed source's SSL certificate (for feeds
 exposed over HTTPS). This option is ignored if ``ssl_verify`` is false.

``ssl_client_cert``
 Certificate used as the client certificate when synchronizing the repository.
 This is used to communicate authentication information to the feed source.
 The value to this option must be the full path to the certificate. The specified
 file may be the certificate itself or a single file containing both the certificate
 and private key.

``ssl_client_key``
 Private key to the certificate specified in ``ssl_client_cert``, assuming it is not
 included in the certificate file itself.

``proxy_url``
 Indicates the URL to use as a proxy server when synchronizing this repository.

``proxy_port``
 Port to connect to on the proxy server.

``proxy_user``
 Username to pass to the proxy server if it requires authentication.

``proxy_pass``
 Password to use for proxy server authentication.

``max_speed``
 Limit the Max speed in KB/sec per thread during package downloads; defaults to None

``verify_checksum``
 If True, as the repository is synchronized the checksum of each file will be
 verified against the metadata's expectation. Valid values to this option are
 ``True`` and ``False``; defaults to ``True``.

``verify_size``
 If true, as the repository is synchronized the size of each file will be verified
 against the metadata's expectation. Valid values to this option are ``True``
 and ``False``; defaults to ``True``.

``num_threads``
 Number of threads used when synchronizing the repository. This count controls
 the download threads themselves and has no bearing on the number of operations
 the Pulp server can execute at a given time; defaults to ``1``.

``newest``
 Option indicating if only the newest version of each package should be downloaded
 during synchronization. Valid values to this option are ``True`` and ``False``;
 defaults to ``True``.

``remove_old``
 If true, as the repository is synchronized, old rpms will be removed. Valid values
 to this option are ``True`` and ``False``; defaults to ``False``

``num_old_packages``
 Count indicating how many old rpm versions to retain; defaults to 0. This count
 only takes effect when ``remove_old`` option is set to ``True``.

``purge_orphaned``
 If True, as the repository is synchronized, packages no longer available from the
 source repository will be deleted; defaults to ``True``.

``skip``
  List of content types to be skipped during the repository synchronization.
  If unspecified, all types will be synchronized. Valid values are: rpm, drpm,
  distribution, errata, packagegroup; default is [].

``checksum_type``
 checksum type to use for metadata generation; defaults to source checksum type of ``sha256``.

``num_retries``
 Number of times to retry before declaring an error during repository synchronization;
 defaults to ``2``.