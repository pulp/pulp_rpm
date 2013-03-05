===========
ISO Plugins
===========

ISO Type
========

The ISO Plugins only have one type, the ISO. The ISO type's ID is ``iso``.

The following are the supported unit types for the Yum and ISO plugins. Each unit has a
unit type and metadata component. Unit type is a unique combination of fields,
and metadata constitutes the rest of the information associated to the unit.

Unit Key
^^^^^^^^

The unit key for the ISO type is ``['name', 'checksum', 'size']``. Each of these attributes is described below.

``name``
This is the filename of the ISO.

``checksum``
This is the `SHA-256 <http://en.wikipedia.org/wiki/SHA-2>`_ checksum of the ISO file.

``size``
This is the size in bytes of the ISO file.

Metadata
^^^^^^^^

ISOs have no additional metadata outside of the unit key.

ISO Importer
============

The ISO Importer can be used to sync an ISO repository with an upstream feed. The ISO Importer id is
``iso_importer``.

Configuration Parameters
------------------------

The following configuration parameters are all optional, and can be used to determine the behavior of the ISO
importer.

ISO Distributor
===============

The ISO distributor can be used to publish available ISOs in an ISO repository over http or https. It is
distinct from the `export_distributor`. The ISO Distributor id is ``iso_distributor``.

Configuration Parameters
------------------------

The following configuration parameters can be used to determine the behavior of the ISO distributor.
