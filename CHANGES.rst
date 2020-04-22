=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/en/3.0/nightly/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

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

- `#5207 <https://pulp.plan.io/issues/5207>`_, `#5455 <https://pulp.plan.io/issues/5455>`_, `#6312 <https://pulp.plan.io/issues/6312>`_, `#6313 <https://pulp.plan.io/issues/6313>`_, `#6339 <https://pulp.plan.io/issues/6339>`_, `#6363 <https://pulp.plan.io/issues/6363>`_, `#6442 <https://pulp.plan.io/issues/6442>`_, `#6155 <https://pulp.plan.io/issues/6155>`_, `#6297 <https://pulp.plan.io/issues/6297>`_, `#6300 <https://pulp.plan.io/issues/6300>`_


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


