===================
Export Distributors
===================

There are two export distributors. One that exports a single repository, and another that exports
a repository group. The export distributors can export the repository or repository group as ISO
images, or to the directory of your choice as one or more yum repositories. The repository
distributor uses the ID ``export_distributor``. The repository group distributor uses the ID
``group_export_distributor``. Exported repository ISOs will be published over HTTP or HTTPS at
the path ``/pulp/exports/repo/<repo-id>/``, and exported repository group ISOs can be found at
``/pulp/exports/repo_group/<group-id>/``.

Configuration Parameters
========================

The following options are available when configuring the export distributors.

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

``start_date``
 Any content that was associated with the repository before this date will be excluded in the generated
 ISO. Furthermore, the incremental export process exports errata and rpm metadata as JSON documents, and
 no repo metadata is generated. The date should be in standard ISO8601 format. For example,
 "2010-01-01T12:00:00".

``end_date``
 Any content that was associated with the repository after this date will be excluded in the generated
 ISO. Furthermore, the incremental export process exports errata and rpm metadata as JSON documents,
 and no repo metadata is generated. The date should be in standard ISO8601 format. For example,
 "2010-01-01T12:00:00".

``iso_prefix``
 Prefix to be used in naming the generated ISO. The ISO will be named like this:
 ``<prefix>-<timestamp>-<disc_number>.iso``. The default is the repository or group id. The prefix
 should only contain alphanumeric characters, dashes, and underscores.

``skip``
 List of content types to skip during the creation of the ISO.
 If unspecified, all types will be published. Valid values are: ``rpm``, ``drpm``, ``srpm``,
 ``distribution``, ``package_group``, and ``erratum``.

``iso_size``
 An integer, which is the maximum size of the generated ISO images in megabytes. In this case, 1
 megabyte is 1 * 1024 * 1024 bytes. This will default to 4380 megabytes (4380 * 1024 * 1024 bytes,
 to be exact) if it is not specified, which should fit on a single layer DVD.

``export_dir``
 A full path to an export directory. If this option is specified, the repositories are not placed in
 ISO images and published over HTTP or HTTPS. Instead, they are written to the export directory.
 This option is useful if exporting to an external hard drive, for example.

``relative_url``
 Relative path at which the repository will be served when exported. If this option is specified with
 ``export_dir``, this will become the exported subdirectory name instead of the default, which is the
 repository id.

``manifest``
 If this boolean is True, a PULP_MANIFEST file will be created in the directory where ISOs are
 created. This allows the ISO importer to directly import what was published. Defaults to False.
