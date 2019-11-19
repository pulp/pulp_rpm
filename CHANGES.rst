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


