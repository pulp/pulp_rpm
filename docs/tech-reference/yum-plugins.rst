===========
Yum Plugins
===========

Yum Types
=========

The following are the supported unit types for the Yum plugins. Each unit has a
unit type and metadata component. Unit type is a unique combination of fields,
and metadata constitutes the rest of the information associated to the unit. The order of the unit fields is
significant (and they are listed in order), as they together represent the unit key.

RPM
----

The RPM's ID is ``rpm``.

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

The SRPM's ID is ``srpm``.

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

The DRPM's ID is ``drpm``.

Unit Key
^^^^^^^^
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
^^^^^^^^
``size``
 Size of the drpm

``sequence``
 delta rpm sequence

``new_package``
 new rpm package associated with the drpm package

Errata
------

The Erratum's ID is ``erratum``.

Unit Key
^^^^^^^^

``id``
 Erratum ID string

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

``from``
 Typically an email address of the erratum issuer

``pushcount``
 Number of times the erratum has been pushed

``reboot_suggested``
 Flag indicating if this erratum is installed it will require a reboot of the system

Distribution
------------

The distribution type's ID is ``distribution``.

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
^^^^^^^^

``files``
 Files associated with the distribution tree.

``timestamp``
 The ``timestamp`` value as taken from the treeinfo file.

Package Group
-------------

The Package Group's ID is ``package_group``.

Unit Key
^^^^^^^^
``id``
 Package group ID

``repo_id``
 Repository ID the package group ID is associated

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

The Package Group Category's ID is ``package_category``.

Unit Key
^^^^^^^^
``id``
 Package group category ID

``repo_id``
 Repository ID to which the package group category ID is associated


Metadata
^^^^^^^^
``name``
 Name of the package group category

``description``
 Description of the package group category

``display_order``
 Display order of the package group category

``packagegroupids``
 Package group IDs associated with the package category


Package Group Environment
-------------------------

The Package Group Environment's ID is ``package_environment``.

Unit Key
^^^^^^^^
``id``
 Package group Environment ID

``repo_id``
 Repository ID to which the package group category ID is associated


Metadata
^^^^^^^^
``name``
 Name of the package group environment

``translated_name``
 Translated names of the package group environment.  These are saved as a dictionary of locale
 codes to translated names.
 Example format: ``{"zh_TW" : 'KDE Plasma 工作空間'}``

``description``
 Description of the package group environment

``translated_description``
 Translated descriptions of the package group environment.  These are saved as a dictionary of locale
 codes to translated descriptions.
 Example format: ``{"ru" : 'KDE Plasma Workspaces - легко настраиваемый графический интерфейс пользователя, который содержит панель, рабочий стол, системные значки и виджеты рабочего стола, а также множество мощных приложений KDE.'}``

``display_order``
 Display order of the package group environment

``group_ids``
 List of Package group IDs associated with the package environment
 Example format: ``['<group_id_1>','<group_id_2>']``

``options``
 Package group IDs and whether they are default options.  The default flag must be set to either
 `True` or `False`.
 Example format: ``{"group" : <group_id>, "default" : True}``


.. note::
    Package_group, package_category and package environment elements can also be uploaded via comps file.
    For more info see :ref:` upload_comps_xml_file`.


Yum Repo Metadata File
----------------------

The Yum Repo Metadata File's ID is ``yum_repo_metadata_file``.

Unit Key
^^^^^^^^
``repo_id``
 The repository id that this metadata file belongs to

``data_type``
 The type of the metadata file

Metadata
^^^^^^^^
``checksum``
 The checksum of the metadata file

``checksum_type``
 The name of the algorithm used to calculate the ``checksum``


Yum Importer
============

The Yum Importer can be used to sync an RPM repository with an upstream feed. The Yum Importer ID is
``yum_importer``.

Configuration Parameters
------------------------

The following options are available to the yum importer configuration. All
configuration values are optional.

``feed``
 URL where the repository's content will be synchronized from. This can be either
 an HTTP URL or a location on disk represented as a file URL.

``ssl_validation``
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

``proxy_host``
 Indicates the URL to use as a proxy server when synchronizing this repository.

``proxy_port``
 Port to connect to on the proxy server.

``proxy_username``
 Username to pass to the proxy server if it requires authentication.

``proxy_password``
 Password to use for proxy server authentication.

``basic_auth_username``
 Username to pass to the feed URL's server if it requires authentication.

``basic_auth_password``
 Password to use for server authentication.

``query_auth_token``
 An authorization token that will be added to every request made to the feed URL's
 server, which may be required to sync from repositories that use this method of
 authorization (SLES 12, for example).

``max_speed``
 The maximum download speed in bytes/sec for a task (such as a sync);
 defaults to None

``validate``
 If True, as the repository is synchronized the checksum of each file will be
 verified against the metadata's expectation. Valid values to this option are
 ``True`` and ``False``; defaults to ``False``.

``max_downloads``
 Number of threads used when synchronizing the repository. This count controls
 the download threads themselves and has no bearing on the number of operations
 the Pulp server can execute at a given time; defaults to ``1``.

``remove_missing``
 If true, as the repository is synchronized, old rpms will be removed. Valid values
 to this option are ``True`` and ``False``; defaults to ``False``

``retain_old_count``
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

``copy_children``
 Supported only as an override config option to a repository copy command, when
 this option is False, the copy command will not attempt to locate and copy child
 packages of errata, groups, or categories. For example, if it is already known
 that all of a group's RPMs are available in the destination repository, it can
 save substantial time to set this to False and thus not have the importer verify
 the presence of each. default is True.

Yum Distributor
===============

The Yum Distributor ID is ``yum_distributor``.

Configuration Parameters
------------------------

The following options are available to the Yum Distributor configuration.

Required Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``http``
 Flag indicating if the repository will be served over a non-SSL connection.
 Valid values to this option are ``True`` and ``False``.

``https``
 Flag indicating if the repository will be served over an SSL connection. If
 this is set to true, the ``https_ca`` option should also be specified to ensure
 consumers bound to this repository have the necessary certificate to validate
 the SSL connection. Valid values to this option are ``True`` and ``False``.

``relative_url``
 Relative path at which the repository will be served.

Optional Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

``generate_sqlite``
 Boolean flag to indicate whether or not sqlite files should be generated during
 a repository publish.  If unspecified it will not run due to the extra time needed to
 perform this operation.

``checksum_type``
 Checksum type to use for metadata generation

``skip``
 List of content types to skip during the repository publish.
 If unspecified, all types will be published. Valid values are: rpm, drpm,
 distribution, errata, packagegroup.
