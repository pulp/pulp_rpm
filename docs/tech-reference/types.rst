Types
=====

The following are the supported unit types for the yum plugin. Each unit has a
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
