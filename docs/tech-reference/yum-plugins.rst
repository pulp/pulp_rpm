===========
Yum Plugins
===========

Yum Types
=========

The following are the supported unit types for the Yum plugins. Each unit has a
unit type and metadata component. Unit type is a unique combination of fields,
and metadata constitutes the rest of the information associated to the unit.

RPM
----

Unit Key
^^^^^^^^

``name``
 Name of the rpm package

``version``
 Version number of the rpm package

``release``
 Release of the rpm package

``epoch``
 Epoch of the rpm package

``arch``
 Arch of the rpm package

``checksumtype``
 Checksum type used to generate the rpm checksum value

``checksum``
 Checksum of the rpm package. This is the checksum of the package itself and not the rpm header checksum

Metadata
^^^^^^^^

``filename``
 Filename of the rpm package

``vendor``
 The organization responsible for building this rpm package

``description``
 A more verbose description of the rpm package

``buildhost``
 The hostname of the build machine on which this package is built

``license``
 The license information of the vendor

``requires``
 Used to include required package dependencies for this rpm package

``provides``
 Used to include rpm provides information

``repodata``
 metadata xml snippets for rpm package. This includes primary, filelists and other xmls.
 Example format: ``{"primary" : <primary_xml>, "filelist" : <filelist_xml>, "other" : <other_xml> }``

SRPM
----

Unit Key
^^^^^^^^

``name``
 Name of the srpm package

``version``
 Version number of the srpm package

``release``
 Release of the srpm package

``epoch``
 Epoch of the srpm package

``arch``
 Arch of the srpm package

``checksumtype``
 Checksum type used to generate the srpm checksum value

``checksum``
 Checksum of the srpm package. This is not the srpm header checksum

Metadata
^^^^^^^^

``filename``
 Filename of the srpm package

``vendor``
 The organization responsible for building this srpm package

``description``
 A more verbose description of the srpm package

``buildhost``
 The hostname of the build machine on which this package is built

``license``
 The license information of the vendor

``requires``
 Used to include the required package dependencies for this srpm package

``provides``
 Used to include srpm provides information

``repodata``
 metadata xml snippets for srpm package. This includes primary, filelists and other xmls.
 Example format: ``{"primary" : <primary_xml>, "filelist" : <filelist_xml>, "other" : <other_xml> }``

DRPM
----

Unit Key
--------
``epoch``
 Epoch of the rpm package

``version``
 Version of the rpm package

``release``
 Release of the rpm package

``filename``
 filename of the drpm package

``checksum``
 checksum of the drpm package

``checksumtype``
 checksum type of the drpm package

Metadata
--------
``size``
 Size of the drpm

``sequence``
 delta rpm sequence

``new_package``
 new rpm package associated with the drpm package

Errata
------

Unit Key
^^^^^^^^

``id``
 Erratum Id string

Metadata
^^^^^^^^

``title``
 Title of the erratum

``description``
 A more detailed description of the erratum

``version``
 Version of the erratum

``release``
 Release of the erratum

``type``
 Type of erratum. Valid values include "security", "bugfix" and "enhancement" erratum

``status``
 Status of the erratum. Example status: "final"

``updated``
 Updated date of the erratum. Expected format "YYYY-MM-DD HH:MM:SS"

``issued``
 Issued date of the erratum. Expected format "YYYY-MM-DD HH:MM:SS"

``severity``
 severity of the erratum. Valid values include "Low", "Moderate", "High"

``references``
 Reference information associated with this erratum

``pkglist``
 Includes package information associated with this erratum

``rights``
 Copyrights information associated for the erratum

``summary``
 Detailed summary information for this erratum

``solution``
 Detailed Solution information for this erratum

``from_str``
 Typically an email address of the erratum issuer

``pushcount``
 Number of times the erratum has been pushed

``reboot_suggested``
 Flag indicating if this erratum is installed it will require a reboot of the system

Distribution
-------------

Unit Key
^^^^^^^^

``id``
 ID of the distribution to be inventoried

``family``
 Family of the distribution tree. For example: Red Hat Enterprise Linux

``variant``
 Variant of the distribution tree. For example: Workstation

``version``
 Version of the distribution tree. For example: 6Server

``arch``
 Arch of the distribution tree. For example: x86_64

Metadata
^^^^^^^^^

``files``
 Files associated with the distribution tree.

Package Group
-------------

Unit Key
^^^^^^^^
``id``
 Package group ID

``repo_id``
 Repository id the package group id is associated

Metadata
^^^^^^^^
``name``
 Name of the package group

``description``
 Description of the package group

``default``
 Include this package group by default. Valid values are `True` and `False`

``user_visible``
 If the packagegroup should be visible when queried. Valid values are `True` and `False`

``langonly``
 Language support groups are selected based on this option

``display_order``
 Display order of the package group

``mandatory_package_names``
 Mandatory package names to include in the package group

``conditional_package_names``
 Conditional package names to include in the package group

``optional_package_names``
 Optional package names to include in the package group

``default_package_names``
 Default package names to include in the package group

Package Group Category
----------------------

Unit Key
^^^^^^^^
``id``
 Package group category ID

``repo_id``
 Repository id to which the package group category id is associated


Metadata
^^^^^^^^
``name``
 Name of the package group category

``description``
 Description of the package group category

``display_order``
 Display order of the package group category

``packagegroupids``
 Package group ids associated with the package category

Yum Importer
============

The Yum Importer can be used to sync an RPM repository with an upstream feed. The Yum Importer id is
``yum_importer``.

Configuration Parameters
------------------------

The following options are available to the yum importer configuration. All
configuration values are optional.

``feed_url``
 URL where the repository's content will be synchronized from. This can be either
 an HTTP URL or a location on disk represented as a file URL.

``ssl_verify``
 Indicates if the server's SSL certificate is verified against the CA certificate
 uploaded. The certificate should be verified against the CA for each client request.
 Has no effect for non-SSL feeds. Valid values to this option are ``True`` and ``False``;
 defaults to ``True``.

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

Yum Distributor
===============

The Yum Distributor id is ``yum_distributor``.

Configuration Parameters 
------------------------

The following options are available to the yum distributor configuration.
In the event a repository does not have a feed, the relative path is also
required. If a feed is specified,the relative path will be derived from it
unless otherwise overridden.

Required Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``relative_url``
 Relative path at which the repository will be served. If this is not specified,
 the relative path is derived from the ``feed_url`` option. For example:
 ``relative_url="rhel_6.2" may translate to publishing at http://localhost/pulp/repos/rhel_6.2``

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
