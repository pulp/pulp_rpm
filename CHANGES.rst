=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

3.13.2 (2021-06-23)

Bugfixes
--------

- Taught sync to process modulemd before packages so is_modular can be known.
  (backported from #8952)
  `#8964 <https://pulp.plan.io/issues/8964>`_


----


3.13.1 (2021-06-23)

Bugfixes
--------

- Fix filelists and changelogs not always being parsed correctly.
  (backported from #8955)
  `#8961 <https://pulp.plan.io/issues/8961>`_
- Fix an AssertionError that could occur when processing malformed (but technically valid) metadata.
  (backported from #8944)
  `#8962 <https://pulp.plan.io/issues/8962>`_


----


3.13.0 (2021-06-17)

Features
--------

- A sync with mirror=True will automatically create a publication using the existing metadata downloaded from the original repo, keeping the repository signature intact.
  `#6353 <https://pulp.plan.io/issues/6353>`_
- Allow the checksum types for packages and metadata to be unspecified, and intelligently decide which ones to use based on context if so.
  `#8722 <https://pulp.plan.io/issues/8722>`_
- Auto-publish no longer modifies distributions.
  Auto-distribute now only requires setting a distribution's ``repository`` field.
  `#8759 <https://pulp.plan.io/issues/8759>`_
- Substantially improved memory consumption while processing extremely large repositories.
  `#8864 <https://pulp.plan.io/issues/8864>`_


Bugfixes
--------

- Fixed publication of a distribution tree if productmd 1.33+ is installed.
  `#8807 <https://pulp.plan.io/issues/8807>`_
- Fixed sync for the case when SRPMs are asked to be skipped.
  `#8812 <https://pulp.plan.io/issues/8812>`_
- Allow static_context to be absent.
  `#8814 <https://pulp.plan.io/issues/8814>`_
- Fixed a trailing slash sometimes being inserted improperly if sles_auth_token is used.
  `#8816 <https://pulp.plan.io/issues/8816>`_


Misc
----

- `#8681 <https://pulp.plan.io/issues/8681>`_


----


3.12.0 (2021-05-19)
===================


Features
--------

- Add support for automatic publishing and distributing.
  `#7622 <https://pulp.plan.io/issues/7622>`_
- Added the ability to synchronize Oracle ULN repositories using ULN remotes.
  You can set an instance wide ULN server base URL using the DEFAULT_ULN_SERVER_BASE_URL setting.
  `#7905 <https://pulp.plan.io/issues/7905>`_


Bugfixes
--------

- Fixed advisory upload-and-merge of already-existing advisories.
  `#7282 <https://pulp.plan.io/issues/7282>`_
- Taught pulp_rpm to order resources on export to avoid deadlocking on import.
  `#7904 <https://pulp.plan.io/issues/7904>`_
- Reduce memory consumption when syncing extremely large repositories.
  `#8467 <https://pulp.plan.io/issues/8467>`_
- Fix error when updating a repository.
  `#8546 <https://pulp.plan.io/issues/8546>`_
- Fixed sync/migration of the kickstart repositories with floating point build_timestamp.
  `#8623 <https://pulp.plan.io/issues/8623>`_
- Fixed a bug where publication used the default metadata checksum type of SHA-256 rather than the one requested by the user.
  `#8644 <https://pulp.plan.io/issues/8644>`_
- Fixed advisory-upload so that a failure no longer breaks uploads forever.
  `#8683 <https://pulp.plan.io/issues/8683>`_
- Fixed syncing XZ-compressed modulemd metadata, e.g. CentOS Stream "AppStream"
  `#8700 <https://pulp.plan.io/issues/8700>`_
- Fixed a workflow where two identical advisories could 'look different' to Pulp.
  `#8716 <https://pulp.plan.io/issues/8716>`_


Improved Documentation
----------------------

- Added workflow documentation for the new ULN remotes.
  `#8426 <https://pulp.plan.io/issues/8426>`_


Misc
----

- `#8509 <https://pulp.plan.io/issues/8509>`_, `#8616 <https://pulp.plan.io/issues/8616>`_, `#8764 <https://pulp.plan.io/issues/8764>`_


----


3.11.1 (2021-05-31)
===================


Bugfixes
--------

- Fixed sync for the case when SRPMs are asked to be skipped.
  (backported from #8812)
  `#8813 <https://pulp.plan.io/issues/8813>`_
- Allow static_context to be absent.
  (backported from #8814)
  `#8815 <https://pulp.plan.io/issues/8815>`_


----


3.11.0 (2021-05-18)
===================


Features
--------

- Taught sync/copy/publish to recognize the new static_context attribute of modules.
  `#8638 <https://pulp.plan.io/issues/8638>`_


Bugfixes
--------

- Fixed syncing XZ-compressed modulemd metadata, e.g. CentOS Stream "AppStream"
  (backported from #8700)
  `#8751 <https://pulp.plan.io/issues/8751>`_
- Fixed a bug where publication used the default metadata checksum type of SHA-256 rather than the one requested by the user.
  (backported from #8644)
  `#8752 <https://pulp.plan.io/issues/8752>`_
- Reduce memory consumption when syncing extremely large repositories.
  (backported from #8467)
  `#8753 <https://pulp.plan.io/issues/8753>`_


----


3.10.0 (2021-03-25)
===================


Features
--------

- Added the ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION configuration option.

  When set to True, overrides Pulp's advisory-merge logic regarding 'suspect'
  advisory collisions at sync and upload time and simply processes the advisory.
  `#8250 <https://pulp.plan.io/issues/8250>`_


Bugfixes
--------

- Taught pulp_rpm how to handle remotes whose URLs do not end in '/'.

  Specifically, some mirrors (e.g. Amazon2) return remotes like this.
  `#7995 <https://pulp.plan.io/issues/7995>`_
- Caught remaining places that needed to know that 'sha' is an alias for 'sha1'.

  Very old versions of createrepo used 'sha' as a checksum-type for 'sha-1'.
  The recent ALLOWED_CHECKSUMS work prevented repositories created this way
  from being synchronized or published.
  `#8052 <https://pulp.plan.io/issues/8052>`_
- Fixed DistributionTree parsing for boolean fields which could cause a failure at sync or migration time.
  `#8245 <https://pulp.plan.io/issues/8245>`_
- Taught advisory-conflict-resolution how to deal with another edge-case.
  `#8249 <https://pulp.plan.io/issues/8249>`_
- Fixed regression in advisory-upload when pkglist included in advisory JSON.
  `#8380 <https://pulp.plan.io/issues/8380>`_
- Fixed the case when no package checksum type cofiguration is provided for publications created outside, not by RPM plugin endpoints. E.g. in pulp-2to3-migration plugin.
  `#8422 <https://pulp.plan.io/issues/8422>`_


Misc
----

- `#7537 <https://pulp.plan.io/issues/7537>`_, `#8223 <https://pulp.plan.io/issues/8223>`_, `#8278 <https://pulp.plan.io/issues/8278>`_, `#8301 <https://pulp.plan.io/issues/8301>`_, `#8392 <https://pulp.plan.io/issues/8392>`_


----


3.9.1 (2021-03-11)
==================


Bugfixes
--------

- Fixed DistributionTree parsing for boolean fields which could cause a failure at sync or migration time.
  `#8374 <https://pulp.plan.io/issues/8374>`_


----


3.9.0 (2021-02-04)
==================


Features
--------

- Make creation of sqlite metadata at Publication time an option, and default to false.
  `#7852 <https://pulp.plan.io/issues/7852>`_
- Check allowed checksum types when publish repository.
  `#7855 <https://pulp.plan.io/issues/7855>`_


Bugfixes
--------

- Fixed content serialization so it displays content checksums.
  `#8002 <https://pulp.plan.io/issues/8002>`_
- Fixing OpenAPI schema for on demand Distribution Trees
  `#8050 <https://pulp.plan.io/issues/8050>`_
- Fix a mistake in RPM copy that could lead to modules being copied when they should not be.
  `#8091 <https://pulp.plan.io/issues/8091>`_
- Fixed a mistake in dependency calculation code which could result in incorrect copy results and errors.
  `#8114 <https://pulp.plan.io/issues/8114>`_
- Fixed a bug that occurs when publishing advisories without an "updated" date set, which includes SUSE advisories.
  `#8162 <https://pulp.plan.io/issues/8162>`_


Improved Documentation
----------------------

- Fixed a mistake in the RPM copy workflow documentation.
  `#7978 <https://pulp.plan.io/issues/7978>`_
- Fixed a mistake in the copy API documentation - dependency solving was described as defaulting to OFF when in fact it defaults to ON.
  `#8009 <https://pulp.plan.io/issues/8009>`_


Misc
----

- `#7843 <https://pulp.plan.io/issues/7843>`_


----


3.8.0 (2020-11-12)
==================


Features
--------

- Added new fields allowing users to customize gpgcheck signature options in a publication.
  `#6926 <https://pulp.plan.io/issues/6926>`_


Bugfixes
--------

- Fixed re-syncing of custom repository metadata when it was the only change in a repository.
  `#7030 <https://pulp.plan.io/issues/7030>`_
- User should not be able to remove distribution trees, custom repository metadata and comps if they are used in repository.
  `#7431 <https://pulp.plan.io/issues/7431>`_
- Raise ValidationError when other type than JSON is provided during Advisory upload.
  `#7468 <https://pulp.plan.io/issues/7468>`_
- Added handling of HTTP 403 Forbidden during DistributionTree detection.
  `#7691 <https://pulp.plan.io/issues/7691>`_
- Fixed the case when downloads were happening outside of the task working directory during sync.
  `#7698 <https://pulp.plan.io/issues/7698>`_


Improved Documentation
----------------------

- Fixed broken documentation links.
  `#6981 <https://pulp.plan.io/issues/6981>`_
- Added documentation clarification around how checksum_types work during the Publication.
  `#7203 <https://pulp.plan.io/issues/7203>`_
- Added examples how to copy all content.
  `#7494 <https://pulp.plan.io/issues/7494>`_
- Clarified the advanced-copy section.
  `#7705 <https://pulp.plan.io/issues/7705>`_


Misc
----

- `#7414 <https://pulp.plan.io/issues/7414>`_, `#7567 <https://pulp.plan.io/issues/7567>`_, `#7571 <https://pulp.plan.io/issues/7571>`_, `#7650 <https://pulp.plan.io/issues/7650>`_, `#7807 <https://pulp.plan.io/issues/7807>`_


----


3.7.0 (2020-09-23)
==================


Bugfixes
--------

- Remove distribution tree subrepositories when a distribution tree is removed.
  `#7440 <https://pulp.plan.io/issues/7440>`_
- Avoid intensive queries taking place during the handling of the "copy" API web request.
  `#7483 <https://pulp.plan.io/issues/7483>`_
- Fixed "Value too long" error for the distribution tree sync.
  `#7498 <https://pulp.plan.io/issues/7498>`_


Misc
----

- `#7040 <https://pulp.plan.io/issues/7040>`_, `#7422 <https://pulp.plan.io/issues/7422>`_, `#7519 <https://pulp.plan.io/issues/7519>`_


----


3.6.3 (2020-11-19)
==================


Bugfixes
--------

- Fixed duplicate key error after incomplete sync task.
  `#7844 <https://pulp.plan.io/issues/7844>`_


----


3.6.2 (2020-09-04)
==================


Bugfixes
--------

- Fixed a bug where dependency solving did not work correctly with packages that depend on files, e.g. depending on /usr/bin/bash.
  `#7202 <https://pulp.plan.io/issues/7202>`_
- Fixed crashes while copying SRPMs with depsolving enabled.
  `#7290 <https://pulp.plan.io/issues/7290>`_
- Fix sync using proxy server.
  `#7321 <https://pulp.plan.io/issues/7321>`_
- Fix sync from mirrorlist with comments (like fedora's mirrorlist).
  `#7354 <https://pulp.plan.io/issues/7354>`_
- Copying advisories/errata no longer fails if one of the packages is not present in the repository.
  `#7369 <https://pulp.plan.io/issues/7369>`_
- Fixing OpenAPI schema for Variant
  `#7394 <https://pulp.plan.io/issues/7394>`_


----


3.6.1 (2020-08-20)
==================


Bugfixes
--------

- Updated Rest API docs to contain only rpm endpoints.
  `#7332 <https://pulp.plan.io/issues/7332>`_
- Fix sync from local (on-disk) repository.
  `#7342 <https://pulp.plan.io/issues/7342>`_


Improved Documentation
----------------------

- Fix copy script example typos.
  `#7176 <https://pulp.plan.io/issues/7176>`_


----


3.6.0 (2020-08-17)
==================


Features
--------

- Taught advisory-merge to proactively avoid package-collection-name collisions.
  `#5740 <https://pulp.plan.io/issues/5740>`_
- Added the ability for users to import and export distribution trees.
  `#6739 <https://pulp.plan.io/issues/6739>`_
- Added import/export support for remaining advisory-related entities.
  `#6815 <https://pulp.plan.io/issues/6815>`_
- Allow a Remote to be associated with a Repository and automatically use it when syncing the
  Repository.
  `#7159 <https://pulp.plan.io/issues/7159>`_
- Improved publishing performance by around 40%.
  `#7289 <https://pulp.plan.io/issues/7289>`_


Bugfixes
--------

- Prevented advisory-merge from 'reusing' UpdateCollections from the merging advisories.
  `#7291 <https://pulp.plan.io/issues/7291>`_


Misc
----

- `#6937 <https://pulp.plan.io/issues/6937>`_, `#7095 <https://pulp.plan.io/issues/7095>`_, `#7195 <https://pulp.plan.io/issues/7195>`_


----


3.5.1 (2020-08-11)
==================


Bugfixes
--------

- Handle optimize=True and mirror=True on sync correctly.
  `#7228 <https://pulp.plan.io/issues/7228>`_
- Fix copy with depsolving for packageenvironments.
  `#7248 <https://pulp.plan.io/issues/7248>`_
- Taught copy that empty-content means 'copy nothing'.
  `#7284 <https://pulp.plan.io/issues/7284>`_


----


3.5.0 (2020-07-24)
==================


Features
--------

- Add a retention policy feature - when specified, the latest N versions of each package will be kept and older versions will be purged.
  `#5367 <https://pulp.plan.io/issues/5367>`_
- Add support for comparing Packages by EVR (epoch, version, release).
  `#5402 <https://pulp.plan.io/issues/5402>`_
- Added support for syncing from a mirror list feed
  `#6225 <https://pulp.plan.io/issues/6225>`_
- Comps types (PackageCategory, PackageEnvironment, PackageGroup) can copy its children.
  `#6316 <https://pulp.plan.io/issues/6316>`_
- Added support for syncing Suse enterprise repositories with authentication token.
  `#6729 <https://pulp.plan.io/issues/6729>`_


Bugfixes
--------

- Fixed the sync issue for repositories with the same metadata files but different filenames. E.g. productid in RHEL8 BaseOS and Appstream.
  `#5847 <https://pulp.plan.io/issues/5847>`_
- Fixed an issue with an incorrect copy of a distribution tree.
  `#7046 <https://pulp.plan.io/issues/7046>`_
- Fixed a repository deletion when a distribution tree is a part of it.
  `#7096 <https://pulp.plan.io/issues/7096>`_
- Corrected several viewset-filters to be django-filter-2.3.0-compliant.
  `#7103 <https://pulp.plan.io/issues/7103>`_
- Allow only one distribution tree in a repo version at a time.
  `#7115 <https://pulp.plan.io/issues/7115>`_
- API is able to show modular data on advisory collection.
  `#7116 <https://pulp.plan.io/issues/7116>`_


Deprecations and Removals
-------------------------

- Remove PackageGroup, PackageCategory and PackageEnvironment relations to packages and to each other.
  `#6410 <https://pulp.plan.io/issues/6410>`_
- Removed the query parameter relative_path from the API which was used when uploading an advisory
  `#6554 <https://pulp.plan.io/issues/6554>`_


Misc
----

- `#7072 <https://pulp.plan.io/issues/7072>`_, `#7134 <https://pulp.plan.io/issues/7134>`_, `#7150 <https://pulp.plan.io/issues/7150>`_


----


3.4.2 (2020-07-16)
==================


Bugfixes
--------

- Fixed CentOS 8 kickstart repository publications.
  `#6568 <https://pulp.plan.io/issues/6568>`_
- Updating API to not return publications that aren't complete.
  `#6974 <https://pulp.plan.io/issues/6974>`_


Improved Documentation
----------------------

- Change fixtures URL in the docs scripts.
  `#6656 <https://pulp.plan.io/issues/6656>`_


Misc
----

- `#6778 <https://pulp.plan.io/issues/6778>`_


----


3.4.1 (2020-06-03)
==================


Bugfixes
--------

- Including requirements.txt on MANIFEST.in
  `#6892 <https://pulp.plan.io/issues/6892>`_


----


3.4.0 (2020-06-01)
==================


Features
--------

- Distributions now serves a config.repo, and when signing is enabled also a public.key, in the base_path.
  `#5356 <https://pulp.plan.io/issues/5356>`_


Bugfixes
--------

- Fixed the duplicated advisory case when only auxiliary fields were updated but not any timestamp or version.
  `#6604 <https://pulp.plan.io/issues/6604>`_
- Fixed dependency solving issue where not all RPM dependencies were coped.
  `#6820 <https://pulp.plan.io/issues/6820>`_
- Make 'last_sync_revision_number' nullable in all migrations.
  `#6861 <https://pulp.plan.io/issues/6861>`_
- Fixed a bug where the behavior of RPM advanced copy with dependency solving differed depending
  on the order of the source-destination repository pairs provided by the user.
  `#6868 <https://pulp.plan.io/issues/6868>`_


Improved Documentation
----------------------

- Added documentation for the RPM copy API.
  `#6332 <https://pulp.plan.io/issues/6332>`_
- Updated the required roles names
  `#6759 <https://pulp.plan.io/issues/6759>`_


Misc
----

- `#4142 <https://pulp.plan.io/issues/4142>`_, `#6514 <https://pulp.plan.io/issues/6514>`_, `#6536 <https://pulp.plan.io/issues/6536>`_, `#6706 <https://pulp.plan.io/issues/6706>`_, `#6777 <https://pulp.plan.io/issues/6777>`_, `#6786 <https://pulp.plan.io/issues/6786>`_, `#6789 <https://pulp.plan.io/issues/6789>`_, `#6801 <https://pulp.plan.io/issues/6801>`_, `#6839 <https://pulp.plan.io/issues/6839>`_, `#6841 <https://pulp.plan.io/issues/6841>`_


----


3.3.2 (2020-05-18)
==================


Bugfixes
--------

- Fix edge case where specifying 'dest_base_version' for an RPM copy did not work properly
  in all circumstances.
  `#6693 <https://pulp.plan.io/issues/6693>`_
- Add a new migration to ensure that 'last_sync_revision_number' is nullable.
  `#6743 <https://pulp.plan.io/issues/6743>`_


----


3.3.1 (2020-05-07)
==================


Bugfixes
--------

- Taught copy to always include specified packages.
  `#6519 <https://pulp.plan.io/issues/6519>`_
- Fixed the upgrade issue, revision number can be empty now.
  `#6662 <https://pulp.plan.io/issues/6662>`_


Misc
----

- `#6665 <https://pulp.plan.io/issues/6665>`_


----


3.3.0 (2020-04-21)
==================


Features
--------

- Add dependency solving for modules and module-defaults.
  `#4162 <https://pulp.plan.io/issues/4162>`_
- Add dependency solving for RPMs.
  `#4761 <https://pulp.plan.io/issues/4761>`_
- Add incremental update -- copying an advisory also copies the RPMs that it references.
  `#4768 <https://pulp.plan.io/issues/4768>`_
- Enable users to publish a signed Yum repository
  `#4812 <https://pulp.plan.io/issues/4812>`_
- Add a criteria parameter to the copy api that can be used to filter content to by copied.
  `#6009 <https://pulp.plan.io/issues/6009>`_
- Added REST API for copying content between repositories.
  `#6018 <https://pulp.plan.io/issues/6018>`_
- Add a content parameter to the copy api that accepts a list of hrefs to be copied.
  `#6019 <https://pulp.plan.io/issues/6019>`_
- Functional test using bindings.
  `#6061 <https://pulp.plan.io/issues/6061>`_
- Added the field 'sha256' to the public API and enabled users to filter content by this field
  `#6187 <https://pulp.plan.io/issues/6187>`_
- Added a config param to copy api which maps multiple sources to destinations.
  `#6268 <https://pulp.plan.io/issues/6268>`_
- Default publish type is alphabetical directory structure under 'Packages' folder.
  `#4445 <https://pulp.plan.io/issues/4445>`_
- Enabled checksum selection when publishing metadata
  `#4458 <https://pulp.plan.io/issues/4458>`_
- Advisory version is considered at conflict resolution time.
  `#5739 <https://pulp.plan.io/issues/5739>`_
- Added support for opensuse advisories.
  `#5829 <https://pulp.plan.io/issues/5829>`_
- Optimize sync to only happen when there have been changes.
  `#6055 <https://pulp.plan.io/issues/6055>`_
- Store the checksum type (sum_type) for advisory packages as an integer, but continue displaying it to the user as a string. This brings the internal representation closer to createrepo_c which uses integers.
  `#6442 <https://pulp.plan.io/issues/6442>`_
- Add support for import/export processing
  `#6473 <https://pulp.plan.io/issues/6473>`_


Bugfixes
--------

- Fix sync for repositories with modular content.
  `#6229 <https://pulp.plan.io/issues/6229>`_
- Properly compare modular content between the versions.
  `#6303 <https://pulp.plan.io/issues/6303>`_
- Deserialize treeinfo files in a scpecific order
  `#6322 <https://pulp.plan.io/issues/6322>`_
- Fixed the repo revision comparison and sync optimization for sub-repos
  `#6367 <https://pulp.plan.io/issues/6367>`_
- Fixed repository metadata that was pointing to wrong file locations.
  `#6399 <https://pulp.plan.io/issues/6399>`_
- Fixed modular advisory publication.
  `#6440 <https://pulp.plan.io/issues/6440>`_
- Fixed advisory publication, missing auxiliary fields were added.
  `#6441 <https://pulp.plan.io/issues/6441>`_
- Fixed publishing of module repodata.
  `#6530 <https://pulp.plan.io/issues/6530>`_


Improved Documentation
----------------------

- Documented bindings installation for a dev environment
  `#6395 <https://pulp.plan.io/issues/6395>`_


Misc
----

- `#5207 <https://pulp.plan.io/issues/5207>`_, `#5455 <https://pulp.plan.io/issues/5455>`_, `#6312 <https://pulp.plan.io/issues/6312>`_, `#6313 <https://pulp.plan.io/issues/6313>`_, `#6339 <https://pulp.plan.io/issues/6339>`_, `#6363 <https://pulp.plan.io/issues/6363>`_, `#6442 <https://pulp.plan.io/issues/6442>`_, `#6155 <https://pulp.plan.io/issues/6155>`_, `#6297 <https://pulp.plan.io/issues/6297>`_, `#6300 <https://pulp.plan.io/issues/6300>`_, `#6560 <https://pulp.plan.io/issues/6560>`_


----


3.2.0 (2020-03-02)
==================


Features
--------

- Add mirror mode for sync endpoint.
  `#5738 <https://pulp.plan.io/issues/5738>`_
- Add some additional not equal filters.
  `#5854 <https://pulp.plan.io/issues/5854>`_
- SRPM can be skipped during the sync.
  `#6033 <https://pulp.plan.io/issues/6033>`_


Bugfixes
--------

- Fix absolute path error when parsing packages stored in S3
  `#5904 <https://pulp.plan.io/issues/5904>`_
- Fix advisory conflict resolution to check current version first.
  `#5924 <https://pulp.plan.io/issues/5924>`_
- Handling float timestamp on treeinfo file
  `#5989 <https://pulp.plan.io/issues/5989>`_
- Raise error when content has overlapping relative_path on the same version
  `#6152 <https://pulp.plan.io/issues/6152>`_
- Fixed an issue causing module and module-default metadata to be stored incorrectly, and added a data migration to fix existing installations.
  `#6191 <https://pulp.plan.io/issues/6191>`_
- Fix REST API for Modulemd "Package" list - instead of returning PKs, return Package HREFs as intended.
  `#6196 <https://pulp.plan.io/issues/6196>`_
- Replace RepositorySyncURL with RpmRepositorySyncURL
  `#6204 <https://pulp.plan.io/issues/6204>`_
- Modulemd dependencies are now stored corectly in DB.
  `#6214 <https://pulp.plan.io/issues/6214>`_


Improved Documentation
----------------------

- Remove the pulp_use_system_wide_pkgs installer variable from the docs. We now set it in the pulp_rpm_prerequisites role. Users can safely leave it in their installer variables for the foreseeable future though.
  `#5992 <https://pulp.plan.io/issues/5992>`_


Misc
----

- `#6030 <https://pulp.plan.io/issues/6030>`_, `#6147 <https://pulp.plan.io/issues/6147>`_


----


3.1.0 (2020-02-03)
==================


Features
--------

- Advisory now support reboot_suggested info.
  `#5737 <https://pulp.plan.io/issues/5737>`_
- Skip unsupported repodata.
  `#6034 <https://pulp.plan.io/issues/6034>`_


Misc
----

- `#5867 <https://pulp.plan.io/issues/5867>`_, `#5900 <https://pulp.plan.io/issues/5900>`_


----


3.0.0 (2019-12-12)
==================


Bugfixes
--------

- Providing a descriptive error message for RPM repos with invalid metadata
  `#4424 <https://pulp.plan.io/issues/4424>`_
- Improve memory performance on syncing.
  `#5688 <https://pulp.plan.io/issues/5688>`_
- Improve memory performance on publishing.
  `#5689 <https://pulp.plan.io/issues/5689>`_
- Resolve the issue which disallowed users to publish uploaded content
  `#5699 <https://pulp.plan.io/issues/5699>`_
- Provide a descriptive error for invalid treeinfo files
  `#5709 <https://pulp.plan.io/issues/5709>`_
- Properly handling syncing when there is no treeinfo file
  `#5732 <https://pulp.plan.io/issues/5732>`_
- Fix comps.xml publish: missing group attributes desc_by_lang, name_by_lang, and default now appear properly.
  `#5741 <https://pulp.plan.io/issues/5741>`_
- Fix error when adding/removing modules to/from a repository.
  `#5746 <https://pulp.plan.io/issues/5746>`_
- Splitting content between repo and sub-repo
  `#5761 <https://pulp.plan.io/issues/5761>`_
- Allow empty string for optional fields for comps.xml content.
  `#5856 <https://pulp.plan.io/issues/5856>`_
- Adds fields from the inherited serializer to comps.xml content types' displayed fields
  `#5857 <https://pulp.plan.io/issues/5857>`_
- Assuring uniqueness on publishing.
  `#5861 <https://pulp.plan.io/issues/5861>`_


Improved Documentation
----------------------

- Document that sync must complete before kicking off a publish
  `#5006 <https://pulp.plan.io/issues/5006>`_
- Add requirements to docs.
  `#5228 <https://pulp.plan.io/issues/5228>`_
- Update installation docs to use system-wide-packages.
  `#5564 <https://pulp.plan.io/issues/5564>`_
- Remove one shot uploader references and info.
  `#5747 <https://pulp.plan.io/issues/5747>`_
- Add 'Rest API' to menu.
  `#5749 <https://pulp.plan.io/issues/5749>`_
- Refactor workflow commands to small scripts.
  `#5750 <https://pulp.plan.io/issues/5750>`_
- Rename 'Errata' to 'Advisory' for consistency.
  `#5751 <https://pulp.plan.io/issues/5751>`_
- Update docs to include modularity and comps support to features.
  Include core-provided browseable distributions in features.
  `#5752 <https://pulp.plan.io/issues/5752>`_
- Update docs to include Tech Preview section
  `#5753 <https://pulp.plan.io/issues/5753>`_
- Update Quickstart page
  `#5754 <https://pulp.plan.io/issues/5754>`_
- Rearrange installation page and add missing information
  `#5755 <https://pulp.plan.io/issues/5755>`_
- Rearrange workflows section to have individual menu items for each content type.
  `#5758 <https://pulp.plan.io/issues/5758>`_
- Add content type descriptions and their specifics.
  `#5759 <https://pulp.plan.io/issues/5759>`_
- Document python build dependencies that must be installed on CentOS / RHEL.
  `#5841 <https://pulp.plan.io/issues/5841>`_


Misc
----

- `#5325 <https://pulp.plan.io/issues/5325>`_, `#5693 <https://pulp.plan.io/issues/5693>`_, `#5701 <https://pulp.plan.io/issues/5701>`_, `#5757 <https://pulp.plan.io/issues/5757>`_, `#5853 <https://pulp.plan.io/issues/5853>`_


----


3.0.0rc1 (2019-11-19)
=====================


Features
--------

- Support for advisory upload.
  `#4012 <https://pulp.plan.io/issues/4012>`_
- Ensure there are no advisories with the same id in a repo version.

  In case where there are two advisories with the same id, either
  one of them is chosen, or they are merged, or there is an error raised
  if there is no way to resolve advisory conflict.
  `#4295 <https://pulp.plan.io/issues/4295>`_
- No duplicated content can be present in a repository version.
  `#4898 <https://pulp.plan.io/issues/4898>`_
- Added sync and publish support for comps.xml types.
  `#5495 <https://pulp.plan.io/issues/5495>`_
- Add/remove RPMs when a repo's modulemd gets added/removed
  `#5526 <https://pulp.plan.io/issues/5526>`_
- Make repositories "typed". Repositories now live at a detail endpoint. Sync is performed by POSTing to {repo_href}/sync/ remote={remote_href}.
  `#5625 <https://pulp.plan.io/issues/5625>`_
- Adding `sub_repo` field to `RpmRepository`
  `#5627 <https://pulp.plan.io/issues/5627>`_


Bugfixes
--------

- Fix publication for sub repos
  `#5630 <https://pulp.plan.io/issues/5630>`_
- Fix ruby bindings for UpdateRecord.
  `#5650 <https://pulp.plan.io/issues/5650>`_
- Fix sync of a repo which contains modules and advisories.
  `#5652 <https://pulp.plan.io/issues/5652>`_
- Fix 404 when repo remote URL is without trailing slash.
  `#5655 <https://pulp.plan.io/issues/5655>`_
- Check that sections exist before parsing them.
  `#5669 <https://pulp.plan.io/issues/5669>`_
- Stopping to save JSONFields as String.
  `#5671 <https://pulp.plan.io/issues/5671>`_
- Handling missing trailing slashes on kickstart tree fetching
  `#5677 <https://pulp.plan.io/issues/5677>`_
- Not require `ref_id` and `title` for `UpdateReference`
  `#5692 <https://pulp.plan.io/issues/5692>`_
- Refactor treeinfo handling and fix publication for kickstarts
  `#5729 <https://pulp.plan.io/issues/5729>`_


Deprecations and Removals
-------------------------

- Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

  Creating / listing / editing / deleting RPM repositories is now performed on /pulp/api/v3/rpm/rpm/ instead of /pulp/api/v3/repositories/. Only RPM content can be present in a RPM repository, and only a RPM repository can hold RPM content.
  `#5625 <https://pulp.plan.io/issues/5625>`_
- Remove plugin managed repos
  `#5627 <https://pulp.plan.io/issues/5627>`_
- Rename endpoints for content to be in plural form consistently

  Endpoints removed -> added:

  /pulp/api/v3/content/rpm/modulemd/ -> /pulp/api/v3/content/rpm/modulemds/
  /pulp/api/v3/content/rpm/packagecategory/ -> /pulp/api/v3/content/rpm/packagecategories/
  /pulp/api/v3/content/rpm/packageenvironment/ -> /pulp/api/v3/content/rpm/packageenvironments/
  /pulp/api/v3/content/rpm/packagegroup/ -> /pulp/api/v3/content/rpm/packagegroups/
  `#5679 <https://pulp.plan.io/issues/5679>`_
- Rename module-defaults content endpoint for consistency

  Endpoints removed -> added:

  /pulp/api/v3/content/rpm/modulemd-defaults/ -> /pulp/api/v3/content/rpm/modulemd_defaults/
  `#5680 <https://pulp.plan.io/issues/5680>`_
- Remove /pulp/api/v3/rpm/copy/ endpoint

  Removed the /pulp/api/v3/rpm/copy/ endpoint. To copy all content now with typed repos, use the
  modify endpoint on a repository.
  `#5681 <https://pulp.plan.io/issues/5681>`_


Misc
----

- `#3308 <https://pulp.plan.io/issues/3308>`_, `#4295 <https://pulp.plan.io/issues/4295>`_, `#5423 <https://pulp.plan.io/issues/5423>`_, `#5461 <https://pulp.plan.io/issues/5461>`_, `#5495 <https://pulp.plan.io/issues/5495>`_, `#5506 <https://pulp.plan.io/issues/5506>`_, `#5580 <https://pulp.plan.io/issues/5580>`_, `#5611 <https://pulp.plan.io/issues/5611>`_, `#5663 <https://pulp.plan.io/issues/5663>`_, `#5672 <https://pulp.plan.io/issues/5672>`_, `#5684 <https://pulp.plan.io/issues/5684>`_


----


3.0.0b7 (2019-10-16)
====================


Features
--------

- Convert all the TextFields which store JSON content into Django JSONFields.
  `#5215 <https://pulp.plan.io/issues/5215>`_


Improved Documentation
----------------------

- Change the prefix of Pulp services from pulp-* to pulpcore-*
  `#4554 <https://pulp.plan.io/issues/4554>`_
- Docs update to use `pulp_use_system_wide_pkgs`.
  `#5488 <https://pulp.plan.io/issues/5488>`_


Deprecations and Removals
-------------------------

- Change `_id`, `_created`, `_last_updated`, `_href` to `pulp_id`, `pulp_created`, `pulp_last_updated`, `pulp_href`
  `#5457 <https://pulp.plan.io/issues/5457>`_
- Removing `repository` from `Addon`/`Variant` serializers.
  `#5516 <https://pulp.plan.io/issues/5516>`_
- Moved endpoints for distribution trees and repo metadata files to /pulp/api/v3/content/rpm/distribution_trees/ and /pulp/api/v3/content/rpm/repo_metadata_files/ respectively.
  `#5535 <https://pulp.plan.io/issues/5535>`_
- Remove "_" from `_versions_href`, `_latest_version_href`
  `#5548 <https://pulp.plan.io/issues/5548>`_


----


3.0.0b6 (2019-09-30)
====================


Features
--------

- Add upload functionality to the rpm contents endpoints.
  `#5453 <https://pulp.plan.io/issues/5453>`_
- Synchronize and publish modular content.
  `#5493 <https://pulp.plan.io/issues/5493>`_


Bugfixes
--------

- Add url prefix to plugin custom urls.
  `#5330 <https://pulp.plan.io/issues/5330>`_


Deprecations and Removals
-------------------------

- Removing `pulp/api/v3/rpm/upload/`
  `#5453 <https://pulp.plan.io/issues/5453>`_


Misc
----

- `#5172 <https://pulp.plan.io/issues/5172>`_, `#5304 <https://pulp.plan.io/issues/5304>`_, `#5408 <https://pulp.plan.io/issues/5408>`_, `#5421 <https://pulp.plan.io/issues/5421>`_, `#5469 <https://pulp.plan.io/issues/5469>`_, `#5493 <https://pulp.plan.io/issues/5493>`_


----


3.0.0b5 (2019-09-17)
========================


Features
--------

- Setting `code` on `ProgressBar`.
  `#5184 <https://pulp.plan.io/issues/5184>`_
- Sync and Publish kickstart trees.
  `#5206 <https://pulp.plan.io/issues/5206>`_
- Sync and Publish custom/unknown repository metadata.
  `#5432 <https://pulp.plan.io/issues/5432>`_


Bugfixes
--------

- Use the field relative_path instead of filename in the API calls while creating a content from an artifact
  `#4987 <https://pulp.plan.io/issues/4987>`_
- Fixing sync task failure.
  `#5285 <https://pulp.plan.io/issues/5285>`_


Misc
----

- `#4681 <https://pulp.plan.io/issues/4681>`_, `#5201 <https://pulp.plan.io/issues/5201>`_, `#5202 <https://pulp.plan.io/issues/5202>`_, `#5331 <https://pulp.plan.io/issues/5331>`_, `#5430 <https://pulp.plan.io/issues/5430>`_, `#5431 <https://pulp.plan.io/issues/5431>`_, `#5438 <https://pulp.plan.io/issues/5438>`_


----


3.0.0b4 (2019-07-03)
====================


Features
--------

- Add total counts to the sync progress report.
  `#4503 <https://pulp.plan.io/issues/4503>`_
- Greatly speed up publishing of a repository.
  `#4591 <https://pulp.plan.io/issues/4591>`_
- Add ability to copy content between repositories, content type(s) can be specified.
  `#4716 <https://pulp.plan.io/issues/4716>`_
- Renamed Errata/Update content to Advisory to better match the terminology of the RPM/DNF ecosystem.
  `#4902 <https://pulp.plan.io/issues/4902>`_
- Python bindings are now published nightly and with each release as
  `pulp-rpm-client <https://pypi.org/project/pulp-rpm-client/>`_. Also Ruby bindings are published
  similarly to rubygems.org as `pulp_rpm_client <https://rubygems.org/gems/pulp_rpm_client>`_.
  `#4960 <https://pulp.plan.io/issues/4960>`_
- Override the Remote's serializer to allow policy='on_demand' and policy='streamed'.
  `#5065 <https://pulp.plan.io/issues/5065>`_


Bugfixes
--------

- Require relative_path at the content unit creation time.
  `#4835 <https://pulp.plan.io/issues/4835>`_
- Fix migraitons failure by making models compatible with MariaDB.
  `#4909 <https://pulp.plan.io/issues/4909>`_
- Fix unique index length issue for MariaDB.
  `#4916 <https://pulp.plan.io/issues/4916>`_


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`_ for better release notes.
  `#4875 <https://pulp.plan.io/issues/4875>`_
- Add a docs page about the Python and Ruby bindings.
  `#4960 <https://pulp.plan.io/issues/4960>`_


Misc
----

- `#4117 <https://pulp.plan.io/issues/4117>`_, `#4567 <https://pulp.plan.io/issues/4567>`_, `#4574 <https://pulp.plan.io/issues/4574>`_, `#5064 <https://pulp.plan.io/issues/5064>`_


----


