==================
Export Distributor
==================

The Export Distributor can be used to build an ISO image out of the content available in RPM repositories.
The Export Distributor ID is ``export_distributor``.

Configuration Parameters
========================

The following options are available when configuring the Export Distributor.

Required Configuration Parameters
---------------------------------

``http``
 Flag indicating if the generated ISO will be served over a non-SSL connection.
 Valid values to this option are ``True`` and ``False``. This option is
 required.

``https``
 Flag indicating if the generated ISO will be served over an SSL connection.
 Valid values to this option are ``True`` and ``False``. This option is required.

Optional Configuration Parameters
---------------------------------

``end_date``
 Errata that have a date greater than, but not equal to, this date will be excluded in the generated ISO. The
 date should follow this format: YYYY-MM-DD HH:MM:SS. For example, "2009-03-30 00:00:00".

``iso_prefix``
 Prefix to be used in naming the generated ISO. The ISO will be named like this:
 ``<prefix>-<timestamp>-<disc_number>.iso``. The default is ``pulp-repos``.

``skip``
 List of content types to skip during the creation of the ISO.
 If unspecified, all types will be published. Valid values are: ``rpm``, ``distribution``, and ``errata``.

``start_date``
 Errata that have a date less than, but not equal to, this date will be excluded in the generated ISO. The date
 should follow this format: YYYY-MM-DD HH:MM:SS. For example, "2009-03-30 00:00:00".
