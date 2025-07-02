# Changelog

[//]: # (You should *NOT* be adding new change log entries to this file, this)
[//]: # (file is managed by towncrier. You *may* edit previous change logs to)
[//]: # (fix problems like typo corrections or such.)
[//]: # (To add a new change log entry, please see the contributing docs.)
[//]: # (WARNING: Don't drop the towncrier directive!)

[//]: # (towncrier release notes start)

## 3.31.0 (2025-07-02) {: #3.31.0 }

#### Features {: #3.31.0-feature }

- Added a synchronous RPM upload API. It's available at /pulp/api/v3/content/rpm/packages/upload/.
  [#4027](https://github.com/pulp/pulp_rpm/issues/4027)

#### Bugfixes {: #3.31.0-bugfix }

- Ensure API responses for `Repository.package_signing_fingerprint` returns an empty string instead of null.
  [#3995](https://github.com/pulp/pulp_rpm/issues/3995)
- Significantly improved publish performance (more than double in some cases) by fixing some Django queries.

#### Improved Documentation {: #3.31.0-doc }

- Added an example of uploading all packages inside a repository using the --directory option.
  [#3709](https://github.com/pulp/pulp_rpm/issues/3709)
- Updated the modify guides to reflect a fix in the pulp-cli modify command.
  [#3881](https://github.com/pulp/pulp_rpm/issues/3881)

#### Misc {: #3.31.0-misc }

- [#3985](https://github.com/pulp/pulp_rpm/issues/3985)

---

## 3.30.2 (2025-06-23) {: #3.30.2 }

#### Bugfixes {: #3.30.2-bugfix }

- Ensure API responses for `Repository.package_signing_fingerprint` returns an empty string instead of null.
  [#3995](https://github.com/pulp/pulp_rpm/issues/3995)

---

## 3.30.1 (2025-06-08) {: #3.30.1 }

#### Bugfixes {: #3.30.1-bugfix }

- Significantly improved publish performance (more than double in some cases) by fixing some Django queries.

---

## 3.30.0 (2025-05-12) {: #3.30.0 }

#### Features {: #3.30.0-feature }

- Enabled the checkpoint feature in pulp_rpm.
  [#3907](https://github.com/pulp/pulp_rpm/issues/3907)

#### Bugfixes {: #3.30.0-bugfix }

- Fix a memory consumption issue w/ syncing repositories that contain modules.
  [#3311](https://github.com/pulp/pulp_rpm/issues/3311)
- Fixed RPM signing with chunked uploads
  [#3927](https://github.com/pulp/pulp_rpm/issues/3927)

#### Deprecations and Removals {: #3.30.0-removal }

- Using the 'gpgcheck', 'repo_gpgcheck', 'package_checksum_type', or 'checksum_type' options, which have been deprecated for some time, will no longer have any effect. In the case of 'gpgcheck' or 'repo_gpgcheck', please use the 'repo_config' option instead. In the case of 'package_checksum_type' or 'metadata_checksum_type', please use 'checksum_type' instead.

#### Misc {: #3.30.0-misc }

- 

---

## 3.29.4 (2025-06-23) {: #3.29.4 }

#### Bugfixes {: #3.29.4-bugfix }

- Ensure API responses for `Repository.package_signing_fingerprint` returns an empty string instead of null.
  [#3995](https://github.com/pulp/pulp_rpm/issues/3995)

---

## 3.29.3 (2025-06-08) {: #3.29.3 }

#### Bugfixes {: #3.29.3-bugfix }

- Fixed RPM signing with chunked uploads
  [#3927](https://github.com/pulp/pulp_rpm/issues/3927)
- Significantly improved publish performance (more than double in some cases) by fixing some Django queries.

---

## 3.29.2 (2025-04-23) {: #3.29.2 }

#### Bugfixes {: #3.29.2-bugfix }

- Fix a memory consumption issue w/ syncing repositories that contain modules.
  [#3311](https://github.com/pulp/pulp_rpm/issues/3311)

---

## 3.29.1 (2025-04-04) {: #3.29.1 }

#### Misc {: #3.29.1-misc }

- 

---

## 3.29.0 (2025-03-18) {: #3.29.0 }

#### Features {: #3.29.0-feature }

- Make the layout of the packages in the published repository configurable.
  [#3874](https://github.com/pulp/pulp_rpm/issues/3874)
- Added permissions for set/unset_label on RPM content-types.

  The types that support this new call include:
    * Package
    * UpdateRecord
    * Modulemd
    * ModulemdDefaults
    * ModulemdObsoletes
  [#3896](https://github.com/pulp/pulp_rpm/issues/3896)

#### Bugfixes {: #3.29.0-bugfix }

- Added a retry mechanism for client authentication in ULN-based downloaders to improve connection stability.
  [#3891](https://github.com/pulp/pulp_rpm/issues/3891)
- Reworked content-labeling RBAC to rely on core.manage_content_labels permission.

  This permission must be explicitly granted by assigning the core.content_labeler Role
  to a user.
  [#3910](https://github.com/pulp/pulp_rpm/issues/3910)

---

## 3.28.1 (2025-03-18) {: #3.28.1 }

No significant changes.

---

## 3.28.0 (2025-02-17) {: #3.28.0 }

#### Bugfixes {: #3.28.0-bugfix }

- Honor repository's compression_type for publications unless overridden
  [#3614](https://github.com/pulp/pulp_rpm/issues/3614)
- Declared compatibility against pulpcore<3.70.
  [#3620](https://github.com/pulp/pulp_rpm/issues/3620)
- Fixed the JSONField specification so it doesn't break ruby bindings.
  [#3639](https://github.com/pulp/pulp_rpm/issues/3639)
- Fixed stacktrace from create_modulemd() when trying to report an error.
  [#3756](https://github.com/pulp/pulp_rpm/issues/3756)
- Make it possible to sync repositories without filelists.xml or other.xml metadata
  [#3777](https://github.com/pulp/pulp_rpm/issues/3777)
- Extended PRN support to Advanced Copy API and DistributionTree.
  [#3853](https://github.com/pulp/pulp_rpm/issues/3853)

#### Improved Documentation {: #3.28.0-doc }

- Updated documentation for prune and advanced-copy to use pulp-cli examples.
  [#3622](https://github.com/pulp/pulp_rpm/issues/3622)

#### Misc {: #3.28.0-misc }

- [#3828](https://github.com/pulp/pulp_rpm/issues/3828), [#3854](https://github.com/pulp/pulp_rpm/issues/3854), [#3856](https://github.com/pulp/pulp_rpm/issues/3856)

---

## 3.27.4 (2025-06-08) {: #3.27.4 }

#### Bugfixes {: #3.27.4-bugfix }

- Fixed RPM signing with chunked uploads
  [#3927](https://github.com/pulp/pulp_rpm/issues/3927)
- Significantly improved publish performance (more than double in some cases) by fixing some Django queries.

---

## 3.27.3 (2025-04-23) {: #3.27.3 }

#### Bugfixes {: #3.27.3-bugfix }

- Fix a memory consumption issue w/ syncing repositories that contain modules.
  [#3311](https://github.com/pulp/pulp_rpm/issues/3311)

---

## 3.27.2 (2024-10-17) {: #3.27.2 }

#### Bugfixes {: #3.27.2-bugfix }

- Fixed the JSONField specification so it doesn't break ruby bindings.
  [#3639](https://github.com/pulp/pulp_rpm/issues/3639)
- Fixed stacktrace from create_modulemd() when trying to report an error.
  [#3756](https://github.com/pulp/pulp_rpm/issues/3756)

---

## 3.27.1 (2024-06-20) {: #3.27.1 }


#### Features {: #3.27.1-feature }

- Honor repository's compression_type for publications unless overridden
  [#3614](https://github.com/pulp/pulp_rpm/issues/3614)

#### Bugfixes {: #3.27.1-bugfix }

- Declared compatibility against pulpcore<3.70.
  [#3620](https://github.com/pulp/pulp_rpm/issues/3620)

---

## 3.27.0 (2024-06-16) {: #3.27.0 }


#### Features {: #3.27.0-feature }

- Added /rpm/prune/ endpoint to allow "pruning" old Packages from repositories.
  [#2909](https://github.com/pulp/pulp_rpm/issues/2909)
- Added (tech preview) support for signing RPM packages when uploading to a Repository.
  [#2986](https://github.com/pulp/pulp_rpm/issues/2986)

#### Bugfixes {: #3.27.0-bugfix }

- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)
- Made sync more tolerant of poorly configured webservers.
  [#3599](https://github.com/pulp/pulp_rpm/issues/3599)

---

## 3.26.5 (2025-04-23) {: #3.26.5 }

#### Bugfixes {: #3.26.5-bugfix }

- Fix a memory consumption issue w/ syncing repositories that contain modules.
  [#3311](https://github.com/pulp/pulp_rpm/issues/3311)

---

## 3.26.4 (2025-03-18) {: #3.26.4 }

No significant changes.

---

## 3.26.3 (2024-10-21) {: #3.26.3 }

#### Bugfixes {: #3.26.3-bugfix }

- Fixed the JSONField specification so it doesn't break ruby bindings.
  [#3639](https://github.com/pulp/pulp_rpm/issues/3639)

---

## 3.26.2 (2024-10-17) {: #3.26.2 }

#### Bugfixes {: #3.26.2-bugfix }

- Honor repository's compression_type for publications unless overridden
  [#3614](https://github.com/pulp/pulp_rpm/issues/3614)
- Declared compatibility against pulpcore<3.70.
  [#3620](https://github.com/pulp/pulp_rpm/issues/3620)
- Fixed stacktrace from create_modulemd() when trying to report an error.
  [#3756](https://github.com/pulp/pulp_rpm/issues/3756)

---

## 3.26.1 (2024-06-16) {: #3.26.1 }


#### Bugfixes {: #3.26.1-bugfix }

- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)
- Made sync more tolerant of poorly configured webservers.
  [#3599](https://github.com/pulp/pulp_rpm/issues/3599)

---

## 3.26.0 (2024-05-28) {: #3.26.0 }

### Features

-   Added django admin command to analyse repository disk size.
    [#3003](https://github.com/pulp/pulp_rpm/issues/3003)
-   Added support for `repository-size` management command.
    [#3312](https://github.com/pulp/pulp_rpm/issues/3312)

### Bugfixes

-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)
-   Fixed modulemd upload raising an error when "packages" parameter was passed.
    [#3427](https://github.com/pulp/pulp_rpm/issues/3427)
-   Fixed an issue where the value of gpgcheck wasn't appropriately set on some publications.
    [#3462](https://github.com/pulp/pulp_rpm/issues/3462)
-   Fix publications created by mirror_complete syncs not having checksum_type set properly.
    [#3484](https://github.com/pulp/pulp_rpm/issues/3484)
-   Fixed modulemd_defaults create endpoint not setting the content digest.
    [#3495](https://github.com/pulp/pulp_rpm/issues/3495)

### Improved Documentation

-   Improved pages about Post/Delete Content (from Pulp) and Add/Remove/Copy existing Content (from Repos).
    [#3482](https://github.com/pulp/pulp_rpm/issues/3482)

### Misc

-   [#3445](https://github.com/pulp/pulp_rpm/issues/3445), [#3520](https://github.com/pulp/pulp_rpm/issues/3520), [#3526](https://github.com/pulp/pulp_rpm/issues/3526)

---

## 3.25.6 (2024-10-17) {: #3.25.6 }

#### Bugfixes {: #3.25.6-bugfix }

- Honor repository's compression_type for publications unless overridden
  [#3614](https://github.com/pulp/pulp_rpm/issues/3614)
- Declared compatibility against pulpcore<3.70.
  [#3620](https://github.com/pulp/pulp_rpm/issues/3620)
- Fixed stacktrace from create_modulemd() when trying to report an error.
  [#3756](https://github.com/pulp/pulp_rpm/issues/3756)

---

## 3.25.5 (2024-06-16) {: #3.25.5 }


#### Bugfixes {: #3.25.5-bugfix }

- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)
- Made sync more tolerant of poorly configured webservers.
  [#3599](https://github.com/pulp/pulp_rpm/issues/3599)

#### Misc {: #3.25.5-misc }

- [#3520](https://github.com/pulp/pulp_rpm/issues/3520)

---

## 3.25.4 (2024-05-28) {: #3.25.4 }

### Bugfixes

-   Fixed modulemd upload raising an error when "packages" parameter was passed.
    [#3427](https://github.com/pulp/pulp_rpm/issues/3427)

### Misc

-   [#3526](https://github.com/pulp/pulp_rpm/issues/3526)

---

## 3.25.3 (2024-04-18) {: #3.25.3 }

### Bugfixes

-   Fix publications created by mirror_complete syncs not having checksum_type set properly.
    [#3484](https://github.com/pulp/pulp_rpm/issues/3484)
-   Fixed modulemd_defaults create endpoint not setting the content digest.
    [#3495](https://github.com/pulp/pulp_rpm/issues/3495)

---

## 3.25.2 (2024-04-02) {: #3.25.2 }

### Bugfixes

-   Fixed an issue where the value of gpgcheck wasn't appropriately set on some publications.
    [#3462](https://github.com/pulp/pulp_rpm/issues/3462)

---

## 3.25.1 (2024-02-09) {: #3.25.1 }

### Bugfixes

-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)

---

## 3.25.0 (2024-01-18) {: #3.25.0 }

### Features

-   Added a `compression_type` option to allow publishing metadata files with zstd compression (in addition to the default gzip).
    [#3316](https://github.com/pulp/pulp_rpm/issues/3316)
-   Raised pulpcore requirement to 3.44.1 to fix an RBAC related bug.
    [#3381](https://github.com/pulp/pulp_rpm/issues/3381)

### Bugfixes

-   Added support for preventing unquoted NSVCA numerical values (e.g. `"stream": 2.10`) of having zeros stripped on modulemd YAML files.
    [#3285](https://github.com/pulp/pulp_rpm/issues/3285)
-   Fixed bug about malformed tuple introduced on the removal of sqlite-metadata support (PR #3328).
    [#3351](https://github.com/pulp/pulp_rpm/issues/3351)
-   Fixed server error when trying to create repository with deprecated gpgcheck and repo_gpgcheck.
    [#3357](https://github.com/pulp/pulp_rpm/issues/3357)
-   Fixes bug where RpmPublications couldn't be created when using a non-admin user.
    [#3381](https://github.com/pulp/pulp_rpm/issues/3381)

### Deprecations and Removals

-   Removed the ability to generate sqlite metadata during repository publish.
    [#2457](https://github.com/pulp/pulp_rpm/issues/2457)
-   Removed support for publishing repos with a checksum type of md5, sha1, or sha224
    [#2488](https://github.com/pulp/pulp_rpm/issues/2488)

### Misc

-   [#3345](https://github.com/pulp/pulp_rpm/issues/3345)

---

## 3.24.1 (2024-01-05) {: #3.24.1 }

### Bugfixes

-   Added support for preventing unquoted NSVCA numerical values (e.g. `"stream": 2.10`) of having zeros stripped on modulemd YAML files.
    [#3285](https://github.com/pulp/pulp_rpm/issues/3285)
-   Fixed server error when trying to create repository with deprecated gpgcheck and repo_gpgcheck.
    [#3357](https://github.com/pulp/pulp_rpm/issues/3357)

---

## 3.24.0 (2023-11-03) {: #3.24.0 }

### Features

-   Added pulpcore 3.40 compatibility.
-   Added ability to customize config .repo file.
    [#2295](https://github.com/pulp/pulp_rpm/issues/2295)
-   Added new json field repo_config that can be used to configure .repo file
    [#2902](https://github.com/pulp/pulp_rpm/issues/2902)
-   Added new json field `repo_config` that can be used to configure .repo file.
    [#2903](https://github.com/pulp/pulp_rpm/issues/2903)

### Bugfixes

-   Improved performance by reducing the number of small queries during exports.
    [#3286](https://github.com/pulp/pulp_rpm/issues/3286)

---

## 3.23.6 (2025-04-23) {: #3.23.6 }

#### Bugfixes {: #3.23.6-bugfix }

- Fix a memory consumption issue w/ syncing repositories that contain modules.
  [#3311](https://github.com/pulp/pulp_rpm/issues/3311)

---

## 3.23.5 (2025-03-18) {: #3.23.5 }

#### Bugfixes {: #3.23.5-bugfix }

- Fixed stacktrace from create_modulemd() when trying to report an error.
  [#3756](https://github.com/pulp/pulp_rpm/issues/3756)

---

## 3.23.4 (2024-06-16) {: #3.23.4 }


#### Bugfixes {: #3.23.4-bugfix }

- Fixed modulemd upload raising an error when "packages" parameter was passed.
  [#3427](https://github.com/pulp/pulp_rpm/issues/3427)
- Fixed modulemd_defaults create endpoint not setting the content digest.
  [#3495](https://github.com/pulp/pulp_rpm/issues/3495)
- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)
- Made sync more tolerant of poorly configured webservers.
  [#3599](https://github.com/pulp/pulp_rpm/issues/3599)

---

## 3.23.3 (2024-02-09) {: #3.23.3 }

### Bugfixes

-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)

---

## 3.23.2 (2024-01-27) {: #3.23.2 }

No significant changes.

---

## 3.23.1 (2024-01-26) {: #3.23.1 }

### Bugfixes

-   Added support for preventing unquoted NSVCA numerical values (e.g. `"stream": 2.10`) of having zeros stripped on modulemd YAML files.
    [#3285](https://github.com/pulp/pulp_rpm/issues/3285)

---

## 3.23.0 (2023-10-13) {: #3.23.0 }

### Features

-   Added NOCACHE_LIST config to enable specifying files to be served with a no-cache header.

    By default, repomd.xml, repomd.key, and repomd.key.asc are served with
    Cache-control: no-cache.
    [#2947](https://github.com/pulp/pulp_rpm/issues/2947)

-   Added to the distribution generate_repo_config field specifying whether Pulp should generate
    `*.repo` files. Defaults to False.
    [#2985](https://github.com/pulp/pulp_rpm/issues/2985)

-   Added a `filename` filter to package list endpoint.
    [#3215](https://github.com/pulp/pulp_rpm/issues/3215)

-   Adjusted default access policies for new labels api.
    [#3243](https://github.com/pulp/pulp_rpm/issues/3243)

### Bugfixes

-   Fixed a deadlock during concurrent syncs of rpm-repos that need data fixups.
    [#2980](https://github.com/pulp/pulp_rpm/issues/2980)
-   Don't write invalid characters to a repo id, even if the distro name contains them.
    [#3170](https://github.com/pulp/pulp_rpm/issues/3170)
-   Made 0048 migration more robust in the face of unexpected data.
    [#3177](https://github.com/pulp/pulp_rpm/issues/3177)
-   Stopped package upload to parse the artifact twice.
    [#3183](https://github.com/pulp/pulp_rpm/issues/3183)
-   Remove the non functional `retrieve` logic from advisories upload, fixing a bug that appeared
    with pulpcore >= 3.29.
    [#3195](https://github.com/pulp/pulp_rpm/issues/3195)
-   Made 0049 migration more robust in the face of unexpected data.
    [#3196](https://github.com/pulp/pulp_rpm/issues/3196)
-   Adjust modules uniqueness to allow two modules with same NSVCA but different snippet content.
    [#3241](https://github.com/pulp/pulp_rpm/issues/3241)
-   Improved performance of exports significantly in some circumstances by optimizing a query.
    [#3259](https://github.com/pulp/pulp_rpm/issues/3259)
-   Fixed sporadic error due to to set domain on non-Content objects at sync time.
    [#3275](https://github.com/pulp/pulp_rpm/issues/3275)

### Misc

-   [#3217](https://github.com/pulp/pulp_rpm/issues/3217), [#3225](https://github.com/pulp/pulp_rpm/issues/3225), [#3226](https://github.com/pulp/pulp_rpm/issues/3226), [#3234](https://github.com/pulp/pulp_rpm/issues/3234), [#3254](https://github.com/pulp/pulp_rpm/issues/3254)

---

## 3.22.9 (2025-03-18) {: #3.22.9 }

#### Bugfixes {: #3.22.9-bugfix }

- Fixed stacktrace from create_modulemd() when trying to report an error.
  [#3756](https://github.com/pulp/pulp_rpm/issues/3756)

---

## 3.22.8 (2024-06-16) {: #3.22.8 }


#### Bugfixes {: #3.22.8-bugfix }

- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)

---

## 3.22.7 (2024-02-09) {: #3.22.7 }

### Bugfixes

-   Added support for preventing unquoted NSVCA numerical values (e.g. `"stream": 2.10`) of having zeros stripped on modulemd YAML files.
    [#3285](https://github.com/pulp/pulp_rpm/issues/3285)
-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)

---

## 3.22.6 (2023-10-16) {: #3.22.6 }

### Bugfixes

-   Fixed sporadic error due to to set domain on non-Content objects at sync time.
    [#3275](https://github.com/pulp/pulp_rpm/issues/3275)
-   Improved performance by reducing the number of small queries during exports.
    [#3286](https://github.com/pulp/pulp_rpm/issues/3286)

### Misc

-   [#3254](https://github.com/pulp/pulp_rpm/issues/3254)

---

## 3.22.5 (2023-09-29) {: #3.22.5 }

### Bugfixes

-   Improved performance of exports significantly in some circumstances by optimizing a query.
    [#3259](https://github.com/pulp/pulp_rpm/issues/3259)

---

## 3.22.4 (2023-09-18) {: #3.22.4 }

### Misc

-   [#3225](https://github.com/pulp/pulp_rpm/issues/3225), [#3226](https://github.com/pulp/pulp_rpm/issues/3226)

---

## 3.22.3 (2023-07-26) {: #3.22.3 }

### Bugfixes

-   Stopped package upload to parse the artifact twice.
    [#3183](https://github.com/pulp/pulp_rpm/issues/3183)
-   Remove the non functional `retrieve` logic from advisories upload, fixing a bug that appeared
    with pulpcore >= 3.29.
    [#3195](https://github.com/pulp/pulp_rpm/issues/3195)
-   Made 0049 migration more robust in the face of unexpected data.
    [#3196](https://github.com/pulp/pulp_rpm/issues/3196)

---

## 3.22.2 (2023-07-06) {: #3.22.2 }

### Bugfixes

-   Made 0048 migration more robust in the face of unexpected data.
    [#3177](https://github.com/pulp/pulp_rpm/issues/3177)

---

## 3.22.1 (2023-06-14) {: #3.22.1 }

### Bugfixes

-   Fixed a deadlock during concurrent syncs of rpm-repos that need data fixups.
    [#2980](https://github.com/pulp/pulp_rpm/issues/2980)
-   Don't write invalid characters to a repo id, even if the distro name contains them.
    [#3170](https://github.com/pulp/pulp_rpm/issues/3170)

---

## 3.22.0 (2023-06-12) {: #3.22.0 }

### Features

-   Added support for Domains.
    [#3008](https://github.com/pulp/pulp_rpm/issues/3008)

---

## 3.21.1 (2023-07-06) {: #3.21.1 }

### Bugfixes

-   Fixed a deadlock during concurrent syncs of rpm-repos that need data fixups.
    [#2980](https://github.com/pulp/pulp_rpm/issues/2980)
-   Made 0048 migration more robust in the face of unexpected data.
    [#3177](https://github.com/pulp/pulp_rpm/issues/3177)

---

## 3.21.0 (2023-05-17) {: #3.21.0 }

### Features

-   Declares (and requires at least) pulpcore/3.25 compatibility.
    [#3151](https://github.com/pulp/pulp_rpm/issues/3151)

### Improved Documentation

-   Fixed infinite loading when searching for specific terms.
    [#3150](https://github.com/pulp/pulp_rpm/issues/3150)

---

## 3.20.0 (2023-05-05) {: #3.20.0 }

### Features

-   The package upload feature was changed to allow the upload of packages which are already
    uploaded - in this scenario, the API will display the existing package as if it had just
    been created.
    [#2764](https://github.com/pulp/pulp_rpm/issues/2764)
-   Added the ability to replicate RPM distributions/repositories from an upstream Pulp instance.
    [#2995](https://github.com/pulp/pulp_rpm/issues/2995)
-   Added a new setting `RPM_METADATA_USE_REPO_PACKAGE_TIME` that will set the primary.xml timestamp
    of each package to when the package was added to the repo rather than when the package first
    appeared in Pulp.
    [#3009](https://github.com/pulp/pulp_rpm/issues/3009)
-   Added more filter options on the packages API.
    [#3135](https://github.com/pulp/pulp_rpm/issues/3135)

### Bugfixes

-   Publish all metadata with a stable sort order. This should reduce artifact churn when certain metadata files are published repeatedly unchanged.
    [#2752](https://github.com/pulp/pulp_rpm/issues/2752)
-   Fixed a failure that can occur during migration from 3.17 to 3.18
    [#2952](https://github.com/pulp/pulp_rpm/issues/2952)
-   Fix a minor module metadata parsing regression that broke Pulp-to-Pulp sync in some scenarios.
    [#2961](https://github.com/pulp/pulp_rpm/issues/2961)
-   Stopped publishing updateinfo.xml when there are no advisories.
    [#2967](https://github.com/pulp/pulp_rpm/issues/2967)
-   Fixed 0044_noartifact_modules migration that was failing with object storage.
    [#2988](https://github.com/pulp/pulp_rpm/issues/2988)
-   Loosen modulemd validation to allow version numbers that have string type but represent integers
    [#2998](https://github.com/pulp/pulp_rpm/issues/2998)
-   Fixed a regression in 3.19 which resulted in unintentional API changes and problems with "depsolving" repo copy.
    [#3012](https://github.com/pulp/pulp_rpm/issues/3012)
-   Fix import/export not importing modulemd_packages data with ManyToMany relationship.
    [#3019](https://github.com/pulp/pulp_rpm/issues/3019)
-   Fix relative path and location href mismatch of the uploaded rpm caused by filename and rpm header mismatch. Clients are getting HTTP 404 Not Found error when downloading the rpm.
    [#3039](https://github.com/pulp/pulp_rpm/issues/3039)
-   Fix a bug with copying modules with depsolving enabled - dependencies were not copied.
    [#3119](https://github.com/pulp/pulp_rpm/issues/3119)
-   Fix a bug for certain repos (e.g. mercurial) relating to how modules are handled.
    [#3121](https://github.com/pulp/pulp_rpm/issues/3121)
-   Fix an issue where the name of UpdateCollection is not defined and might affect import/export, and added a data repair script (pulpcore-manager rpm-datarepair 3127).
    [#3127](https://github.com/pulp/pulp_rpm/issues/3127)
-   Fixes an accidental change that was made to how "profiles" are formatted in the modulemd API.
    [#3131](https://github.com/pulp/pulp_rpm/issues/3131)

### Misc

-   [#2242](https://github.com/pulp/pulp_rpm/issues/2242), [#2867](https://github.com/pulp/pulp_rpm/issues/2867), [#2868](https://github.com/pulp/pulp_rpm/issues/2868), [#2869](https://github.com/pulp/pulp_rpm/issues/2869), [#2870](https://github.com/pulp/pulp_rpm/issues/2870), [#2871](https://github.com/pulp/pulp_rpm/issues/2871), [#2873](https://github.com/pulp/pulp_rpm/issues/2873), [#2874](https://github.com/pulp/pulp_rpm/issues/2874), [#2875](https://github.com/pulp/pulp_rpm/issues/2875), [#2876](https://github.com/pulp/pulp_rpm/issues/2876), [#2877](https://github.com/pulp/pulp_rpm/issues/2877), [#2878](https://github.com/pulp/pulp_rpm/issues/2878), [#2879](https://github.com/pulp/pulp_rpm/issues/2879), [#2880](https://github.com/pulp/pulp_rpm/issues/2880), [#2881](https://github.com/pulp/pulp_rpm/issues/2881), [#2882](https://github.com/pulp/pulp_rpm/issues/2882), [#2883](https://github.com/pulp/pulp_rpm/issues/2883), [#2884](https://github.com/pulp/pulp_rpm/issues/2884), [#2885](https://github.com/pulp/pulp_rpm/issues/2885), [#2887](https://github.com/pulp/pulp_rpm/issues/2887), [#3076](https://github.com/pulp/pulp_rpm/issues/3076), [#3077](https://github.com/pulp/pulp_rpm/issues/3077), [#3078](https://github.com/pulp/pulp_rpm/issues/3078), [#3079](https://github.com/pulp/pulp_rpm/issues/3079), [#3095](https://github.com/pulp/pulp_rpm/issues/3095)

---

## 3.19.13 (2025-03-18) {: #3.19.13 }

#### Bugfixes {: #3.19.13-bugfix }

- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)

---

## 3.19.12 (2024-02-09) {: #3.19.12 }

### Bugfixes

-   Added support for preventing unquoted NSVCA numerical values (e.g. `"stream": 2.10`) of having zeros stripped on modulemd YAML files.
    [#3285](https://github.com/pulp/pulp_rpm/issues/3285)
-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)

---

## 3.19.11 (2023-10-16) {: #3.19.11 }

### Bugfixes

-   Improved performance by reducing the number of small queries during exports.
    [#3286](https://github.com/pulp/pulp_rpm/issues/3286)

### Misc

-   [#3254](https://github.com/pulp/pulp_rpm/issues/3254)

---

## 3.19.10 (2023-09-29) {: #3.19.10 }

### Bugfixes

-   Improved performance of exports significantly in some circumstances by optimizing a query.
    [#3259](https://github.com/pulp/pulp_rpm/issues/3259)

### Misc

-   [#3225](https://github.com/pulp/pulp_rpm/issues/3225), [#3226](https://github.com/pulp/pulp_rpm/issues/3226)

---

## 3.19.9 (2023-07-24) {: #3.19.9 }

### Bugfixes

-   Made 0049 migration more robust in the face of unexpected data.
    [#3196](https://github.com/pulp/pulp_rpm/issues/3196)

---

## 3.19.8 (2023-07-06) {: #3.19.8 }

### Bugfixes

-   Made 0048 migration more robust in the face of unexpected data.
    [#3177](https://github.com/pulp/pulp_rpm/issues/3177)

---

## 3.19.7 (2023-06-14) {: #3.19.7 }

### Bugfixes

-   Fixed a deadlock during concurrent syncs of rpm-repos that need data fixups.
    [#2980](https://github.com/pulp/pulp_rpm/issues/2980)

---

## 3.19.6 (2023-05-05) {: #3.19.6 }

### Bugfixes

-   Fix an issue where the name of UpdateCollection is not defined and might affect import/export, and added a data repair script (ulpcore-manager rpm-datarepair 3127).
    [#3127](https://github.com/pulp/pulp_rpm/issues/3127)
-   Fixes an accidental change that was made to how "profiles" are formatted in the modulemd API.
    [#3131](https://github.com/pulp/pulp_rpm/issues/3131)

---

## 3.19.5 (2023-05-02) {: #3.19.5 }

### Bugfixes

-   Fix a bug with copying modules with depsolving enabled - dependencies were not copied.
    [#3119](https://github.com/pulp/pulp_rpm/issues/3119)
-   Fix a bug for certain repos (e.g. mercurial) relating to how modules are handled.
    [#3121](https://github.com/pulp/pulp_rpm/issues/3121)

---

## 3.19.4 (2023-04-10) {: #3.19.4 }

### Bugfixes

-   Fix import/export not importing modulemd_packages data with ManyToMany relationship.
    [#3019](https://github.com/pulp/pulp_rpm/issues/3019)

### Misc

-   [#2869](https://github.com/pulp/pulp_rpm/issues/2869), [#2873](https://github.com/pulp/pulp_rpm/issues/2873), [#2877](https://github.com/pulp/pulp_rpm/issues/2877), [#2880](https://github.com/pulp/pulp_rpm/issues/2880), [#2883](https://github.com/pulp/pulp_rpm/issues/2883), [#2884](https://github.com/pulp/pulp_rpm/issues/2884), [#2885](https://github.com/pulp/pulp_rpm/issues/2885), [#2887](https://github.com/pulp/pulp_rpm/issues/2887), [#3076](https://github.com/pulp/pulp_rpm/issues/3076)

---

## 3.19.3 (2023-03-29) {: #3.19.3 }

### Bugfixes

-   Fix relative path and location href mismatch of the uploaded rpm caused by filename and rpm header mismatch. Clients are getting HTTP 404 Not Found error when downloading the rpm.
    [#3039](https://github.com/pulp/pulp_rpm/issues/3039)

### Misc

-   [#2867](https://github.com/pulp/pulp_rpm/issues/2867), [#2868](https://github.com/pulp/pulp_rpm/issues/2868), [#2870](https://github.com/pulp/pulp_rpm/issues/2870), [#2871](https://github.com/pulp/pulp_rpm/issues/2871), [#2878](https://github.com/pulp/pulp_rpm/issues/2878), [#2879](https://github.com/pulp/pulp_rpm/issues/2879), [#2882](https://github.com/pulp/pulp_rpm/issues/2882)

---

## 3.19.2 (2023-03-20) {: #3.19.2 }

### Bugfixes

-   Loosen modulemd validation to allow version numbers that have string type but represent integers
    [#2998](https://github.com/pulp/pulp_rpm/issues/2998)
-   Fixed a regression in 3.19 which resulted in unintentional API changes and problems with "depsolving" repo copy.
    [#3012](https://github.com/pulp/pulp_rpm/issues/3012)

### Misc

-   [#2242](https://github.com/pulp/pulp_rpm/issues/2242), [#2876](https://github.com/pulp/pulp_rpm/issues/2876)

---

## 3.19.1 (2023-03-06) {: #3.19.1 }

### Bugfixes

-   Publish all metadata with a stable sort order. This should reduce artifact churn when certain metadata files are published repeatedly unchanged.
    [#2752](https://github.com/pulp/pulp_rpm/issues/2752)
-   Fixed a failure that can occur during migration from 3.17 to 3.18
    [#2952](https://github.com/pulp/pulp_rpm/issues/2952)
-   Fix a minor module metadata parsing regression that broke Pulp-to-Pulp sync in some scenarios.
    [#2961](https://github.com/pulp/pulp_rpm/issues/2961)
-   Stopped publishing updateinfo.xml when there are no advisories.
    [#2967](https://github.com/pulp/pulp_rpm/issues/2967)
-   Fixed 0044_noartifact_modules migration that was failing with object storage.
    [#2988](https://github.com/pulp/pulp_rpm/issues/2988)

### Misc

-   [#2874](https://github.com/pulp/pulp_rpm/issues/2874), [#2881](https://github.com/pulp/pulp_rpm/issues/2881)

---

## 3.19.0 (2023-02-06) {: #3.19.0 }

### Features

-   Add RBAC support for RPM plugin.
    [#2272](https://github.com/pulp/pulp_rpm/issues/2272)
-   Add documentation for RBAC.
    [#2506](https://github.com/pulp/pulp_rpm/issues/2506)
-   Enabled pulp_rpm to take advantage of "create_repositories" at PulpImport time.
    [#2585](https://github.com/pulp/pulp_rpm/issues/2585)
-   Added new condition on uploads to require `repository` field if user is not an admin.
    [#2588](https://github.com/pulp/pulp_rpm/issues/2588)
-   Added "treeinfo" to available skip_types at sync-time. This option
    allows the user to sync a repository without pulling down
    kickstart data and sub-repositories.
    [#2848](https://github.com/pulp/pulp_rpm/issues/2848)

### Bugfixes

-   Fixed concurrent-overlapping-sync of subrepos by making them repository-unique.

    This change is transparent to end-users.
    [#2278](https://github.com/pulp/pulp_rpm/issues/2278)

-   Perform a data repair during the sync process to address a couple of data quality issues. Namely: fix changelogs in some cases where what is saved no longer matches what is synced, and fix packages which were previously incorrectly marked as non-modular.
    [#2643](https://github.com/pulp/pulp_rpm/issues/2643)

-   Deduplicate file entries
    [#2719](https://github.com/pulp/pulp_rpm/issues/2719)

-   Fix recreation of modular snippet when missing.
    [#2735](https://github.com/pulp/pulp_rpm/issues/2735)

-   Allow syncing repos with a compressed comps.xml "group" metadata declared in repomd.xml.
    [#2753](https://github.com/pulp/pulp_rpm/issues/2753)

-   Fix migration from modular artifacts to db snippets.
    [#2777](https://github.com/pulp/pulp_rpm/issues/2777)

-   Fix metadata for users who already attempted to migrate to `3.18.1` unsuccessfully.
    [#2786](https://github.com/pulp/pulp_rpm/issues/2786)

-   Ensured unsupported metadata files are also handled during publish.
    [#2795](https://github.com/pulp/pulp_rpm/issues/2795)

-   Taught RPM how to handle duplicate-advisory-ids at repository-version-create time.
    [#2821](https://github.com/pulp/pulp_rpm/issues/2821)

-   Fix migration of modular snippets from filesystem to DB.
    [#2827](https://github.com/pulp/pulp_rpm/issues/2827)

-   Fix migrations to work on any storage backend.
    [#2843](https://github.com/pulp/pulp_rpm/issues/2843)

-   Fix syncing repos with missing epoch metadata for packages.
    [#2858](https://github.com/pulp/pulp_rpm/issues/2858)

-   Fix an issue where the public key (repomd.xml.key) files generated by Pulp would be empty.
    [#2892](https://github.com/pulp/pulp_rpm/issues/2892)

### Misc

-   [#2718](https://github.com/pulp/pulp_rpm/issues/2718), [#2791](https://github.com/pulp/pulp_rpm/issues/2791), [#2805](https://github.com/pulp/pulp_rpm/issues/2805), [#2832](https://github.com/pulp/pulp_rpm/issues/2832), [#2886](https://github.com/pulp/pulp_rpm/issues/2886), [#2905](https://github.com/pulp/pulp_rpm/issues/2905)

---

## 3.18.21 (2024-06-20) {: #3.18.21 }


#### Bugfixes {: #3.18.21-bugfix }

- Taught tests to find centos8 at vault.centos.org.
  [#3572](https://github.com/pulp/pulp_rpm/issues/3572)
- Fix a flaw that still allowed to add duplicate advisories to a repository version.
  [#3587](https://github.com/pulp/pulp_rpm/issues/3587)

---

## 3.18.20 (2024-02-09) {: #3.18.20 }

### Bugfixes

-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)

---

## 3.18.19 (2023-10-16) {: #3.18.19 }

### Bugfixes

-   Improved performance by reducing the number of small queries during exports.
    [#3286](https://github.com/pulp/pulp_rpm/issues/3286)

### Misc

-   [#3254](https://github.com/pulp/pulp_rpm/issues/3254)

---

## 3.18.18 (2023-09-29) {: #3.18.18 }

### Bugfixes

-   Improved performance of exports significantly in some circumstances by optimizing a query.
    [#3259](https://github.com/pulp/pulp_rpm/issues/3259)

### Misc

-   [#3225](https://github.com/pulp/pulp_rpm/issues/3225), [#3226](https://github.com/pulp/pulp_rpm/issues/3226)

---

## 3.18.17 (2023-06-14) {: #3.18.17 }

### Bugfixes

-   Fixed a deadlock during concurrent syncs of rpm-repos that need data fixups.
    [#2980](https://github.com/pulp/pulp_rpm/issues/2980)

---

## 3.18.16 (2023-05-05) {: #3.18.16 }

### Bugfixes

-   Fix an issue where the name of UpdateCollection is not defined and might affect import/export, and added a data repair script (pulpcore-manager rpm-datarepair 3127).
    [#3127](https://github.com/pulp/pulp_rpm/issues/3127)

---

## 3.18.15 (2023-05-02) {: #3.18.15 }

### Bugfixes

-   Fix a bug with copying modules with depsolving enabled - dependencies were not copied.
    [#3119](https://github.com/pulp/pulp_rpm/issues/3119)

---

## 3.18.14 (2023-04-10) {: #3.18.14 }

### Bugfixes

-   Fix import/export not importing modulemd_packages data with ManyToMany relationship.
    [#3019](https://github.com/pulp/pulp_rpm/issues/3019)

### Misc

-   [#2869](https://github.com/pulp/pulp_rpm/issues/2869), [#2873](https://github.com/pulp/pulp_rpm/issues/2873), [#2877](https://github.com/pulp/pulp_rpm/issues/2877), [#2880](https://github.com/pulp/pulp_rpm/issues/2880), [#2885](https://github.com/pulp/pulp_rpm/issues/2885), [#2887](https://github.com/pulp/pulp_rpm/issues/2887), [#3076](https://github.com/pulp/pulp_rpm/issues/3076)

---

## 3.18.13 (2023-03-29) {: #3.18.13 }

### Bugfixes

-   Fix relative path and location href mismatch of the uploaded rpm caused by filename and rpm header mismatch. Clients are getting HTTP 404 Not Found error when downloading the rpm.
    [#3039](https://github.com/pulp/pulp_rpm/issues/3039)

### Misc

-   [#2242](https://github.com/pulp/pulp_rpm/issues/2242), [#2867](https://github.com/pulp/pulp_rpm/issues/2867), [#2868](https://github.com/pulp/pulp_rpm/issues/2868), [#2870](https://github.com/pulp/pulp_rpm/issues/2870), [#2871](https://github.com/pulp/pulp_rpm/issues/2871), [#2876](https://github.com/pulp/pulp_rpm/issues/2876), [#2878](https://github.com/pulp/pulp_rpm/issues/2878), [#2879](https://github.com/pulp/pulp_rpm/issues/2879), [#2882](https://github.com/pulp/pulp_rpm/issues/2882)

---

## 3.18.12 (2023-03-06) {: #3.18.12 }

### Bugfixes

-   Publish all metadata with a stable sort order. This should reduce artifact churn when certain metadata files are published repeatedly unchanged.
    [#2752](https://github.com/pulp/pulp_rpm/issues/2752)
-   Stopped publishing updateinfo.xml when there are no advisories.
    [#2967](https://github.com/pulp/pulp_rpm/issues/2967)
-   Fixed 0044_noartifact_modules migration that was failing with object storage.
    [#2988](https://github.com/pulp/pulp_rpm/issues/2988)

### Misc

-   [#2874](https://github.com/pulp/pulp_rpm/issues/2874), [#2881](https://github.com/pulp/pulp_rpm/issues/2881), [#2886](https://github.com/pulp/pulp_rpm/issues/2886)

---

## 3.18.11 (2023-02-15) {: #3.18.11 }

### Bugfixes

-   Allow syncing repos with a compressed comps.xml "group" metadata declared in repomd.xml.
    [#2753](https://github.com/pulp/pulp_rpm/issues/2753)

---

## 3.18.10 (2023-01-27) {: #3.18.10 }

### Bugfixes

-   Taught RPM how to handle duplicate-advisory-ids at repository-version-create time.
    [#2821](https://github.com/pulp/pulp_rpm/issues/2821)

### Misc

-   [#2848](https://github.com/pulp/pulp_rpm/issues/2848), [#2905](https://github.com/pulp/pulp_rpm/issues/2905)

---

## 3.18.9 (2022-11-21) {: #3.18.9 }

### Bugfixes

-   Fixed concurrent-overlapping-sync of subrepos by making them repository-unique.

    This change is transparent to end-users.
    [#2278](https://github.com/pulp/pulp_rpm/issues/2278)

-   Fix syncing repos with missing epoch metadata for packages.
    [#2858](https://github.com/pulp/pulp_rpm/issues/2858)

-   Fix an issue where the public key (repomd.xml.key) files generated by Pulp would be empty.
    [#2892](https://github.com/pulp/pulp_rpm/issues/2892)

---

## 3.18.8 (2022-11-07) {: #3.18.8 }

### Bugfixes

-   Fix migrations to work on any storage backend.
    [#2843](https://github.com/pulp/pulp_rpm/issues/2843)

### Misc

-   [#2791](https://github.com/pulp/pulp_rpm/issues/2791), [#2832](https://github.com/pulp/pulp_rpm/issues/2832)

---

## 3.18.7 (2022-10-12) {: #3.18.7 }

No significant changes.

---

## 3.18.6 (2022-10-12) {: #3.18.6 }

### Bugfixes

-   Deduplicate file entries
    [#2719](https://github.com/pulp/pulp_rpm/issues/2719)
-   Fix recreation of modular snippet when missing.
    [#2735](https://github.com/pulp/pulp_rpm/issues/2735)
-   Fix migration of modular snippets from filesystem to DB.
    [#2827](https://github.com/pulp/pulp_rpm/issues/2827)

---

## 3.18.5 (2022-09-30) {: #3.18.5 }

### Misc

-   [#2805](https://github.com/pulp/pulp_rpm/issues/2805)

---

## 3.18.4 (2022-09-29) {: #3.18.4 }

No significant changes.

---

## 3.18.3 (2022-09-27) {: #3.18.3 }

### Bugfixes

-   Perform a data repair during the sync process to address a couple of data quality issues. Namely: fix changelogs in some cases where what is saved no longer matches what is synced, and fix packages which were previously incorrectly marked as non-modular.
    [#2643](https://github.com/pulp/pulp_rpm/issues/2643)
-   Ensured unsupported metadata files are also handled during publish.
    [#2795](https://github.com/pulp/pulp_rpm/issues/2795)

---

## 3.18.2 (2022-09-19) {: #3.18.2 }

### Bugfixes

-   Fix migration from modular artifacts to db snippets.
    [#2777](https://github.com/pulp/pulp_rpm/issues/2777)

---

## 3.18.1 (2022-09-13) {: #3.18.1 }

### Deprecations and Removals

-   Removed "pulp_rpm to take advantage of "create_repositories" at PulpImport time" due to a compatibility issue - it will be shipped in 3.19.
    [#2585](https://github.com/pulp/pulp_rpm/issues/2585)

### Misc

-   [#2771](https://github.com/pulp/pulp_rpm/issues/2771)

---

## 3.18.0 (2022-09-12) {: #3.18.0 }

### Features

-   RPM metadata is now sorted by package name and version information, which slightly improves compression efficiency.
    [#2274](https://github.com/pulp/pulp_rpm/issues/2274)
-   Make `relative_path` optional when uploading a package.
    [#2440](https://github.com/pulp/pulp_rpm/issues/2440)
-   Shows modulemd profiles and description to user.
    [#2456](https://github.com/pulp/pulp_rpm/issues/2456)
-   Support Modulemd obsoletes.
    [#2570](https://github.com/pulp/pulp_rpm/issues/2570)
-   Enabled pulp_rpm to take advantage of "create_repositories" at PulpImport time.
    [#2585](https://github.com/pulp/pulp_rpm/issues/2585)
-   Keep modular metadata in database as a string instead of saving them to the disk.
    [#2621](https://github.com/pulp/pulp_rpm/issues/2621)

### Bugfixes

-   Fixed treeinfo processing to handle some very old treeinfo formats.
    [#2243](https://github.com/pulp/pulp_rpm/issues/2243)
-   Update installation dependencies.
    [#2289](https://github.com/pulp/pulp_rpm/issues/2289)
-   The use of skip_types while performing a sync under the mirror_complete sync policy is now disallowed. Previously it would be silently ignored instead.
    [#2293](https://github.com/pulp/pulp_rpm/issues/2293)
-   Substantial improvements to the memory consumption of syncs, with a modest improvement in time required to sync.
    [#2296](https://github.com/pulp/pulp_rpm/issues/2296)
-   Improved error reporting in one scenario where it could be highly confusing.
    [#2395](https://github.com/pulp/pulp_rpm/issues/2395)
-   Added an exception for a case where repository metadata is incorrect in such a way that it should not be "mirrored", and a warning in other cases. If these warnings / errors are encountered, the party which manages the repo should be contacted. If it is a public repo, an issue can be filed in our tracker, and we will follow up with that party following confirmation of the issue.
    [#2398](https://github.com/pulp/pulp_rpm/issues/2398)
-   Made sure that Pulp doesn't publish repos with duplicate NEVRA in some edge case scenarios.
    [#2407](https://github.com/pulp/pulp_rpm/issues/2407)
-   Taught advisory-conflict-resolution to handle just-EVR-differences in incoming advisory's
    package-list. This solves the case of repositories that update advisories to always have
    the newest versions of RPMs (looking at you, EPEL...).
    [#2422](https://github.com/pulp/pulp_rpm/issues/2422)
-   Fix ULN remote username and password fields which ought to have been write-only and hidden.
    [#2428](https://github.com/pulp/pulp_rpm/issues/2428)
-   Fix the behavior of gpgcheck and repo_gpgcheck options when specified on the repository.
    [#2430](https://github.com/pulp/pulp_rpm/issues/2430)
-   Fixed an issue that could cause orphan cleanup to fail for certain repos.
    [#2459](https://github.com/pulp/pulp_rpm/issues/2459)
-   Fix an issue where package requirements containing an ampersand character in the name might have their data parsed incorrectly, and added a data repair script (pulpcore-manager rpm-datarepair 2460).
    [#2460](https://github.com/pulp/pulp_rpm/issues/2460)
-   Changed the naming of the trim_rpm_changelogs management command to rpm-trim-changelogs to better match with other command names.
    [#2470](https://github.com/pulp/pulp_rpm/issues/2470)
-   Fixed instances of /tmp/ being used instead of the worker's working directory.
    [#2475](https://github.com/pulp/pulp_rpm/issues/2475)
-   Using retain_package_versions (with the required "additive" sync_policy) will now avoid downloading the older packages when synced with download_policy "on_demand", resulting in much faster and more efficient syncs.
    [#2479](https://github.com/pulp/pulp_rpm/issues/2479)
-   Converted RepoMetadataFile.data_type to TextField in order to drop the max_length restriction.
    [#2501](https://github.com/pulp/pulp_rpm/issues/2501)
-   Fixes ACS to not require `name` in bindings.
    [#2504](https://github.com/pulp/pulp_rpm/issues/2504)
-   Fix ACS to update last refreshed time.
    [#2505](https://github.com/pulp/pulp_rpm/issues/2505)
-   Fixed unix timestamps not being parsed correctly for issued and updated dates.
    [#2528](https://github.com/pulp/pulp_rpm/issues/2528)
-   Fix a small FD leak during complete mirror syncs
    [#2624](https://github.com/pulp/pulp_rpm/issues/2624)
-   Fix import/export of Alma linux repositories.
    [#2648](https://github.com/pulp/pulp_rpm/issues/2648)
-   Improved error message for Alternate Content Source refresh when it has insufficient permissions.
    [#2667](https://github.com/pulp/pulp_rpm/issues/2667)
-   Don't raise a fatal error when encountering mostly valid metadata that contains data we don't expect, or data in the wrong places, in situations where it doesn't really matter.
    [#2686](https://github.com/pulp/pulp_rpm/issues/2686)
-   Allow syncing repositories with duplicate NEVRA in mirror_complete mode, but make sure syncing those packages are skipped.
    [#2691](https://github.com/pulp/pulp_rpm/issues/2691)
-   Do not optimize sync if retain-package-versions was set/changed
    [#2704](https://github.com/pulp/pulp_rpm/issues/2704)
-   Fixed a bug were some SLES repos were publishing metadata with missing drpms.
    [#2705](https://github.com/pulp/pulp_rpm/issues/2705)
-   Fixed orphan cleanup error in case Addon(Variant) were pointing to same subrepo.
    [#2733](https://github.com/pulp/pulp_rpm/issues/2733)

### Improved Documentation

-   Added documentation steps to remove content.
    [#2303](https://github.com/pulp/pulp_rpm/issues/2303)

### Deprecations and Removals

-   sqlite metadata support is being deprecated. See [this discourse thread](https://discourse.pulpproject.org/t/planning-to-remove-a-feature-from-the-rpm-plugin-sqlite-metadata/418) for additional details, or to advocate for the continued support of the feature.
    [#2457](https://github.com/pulp/pulp_rpm/issues/2457)

### Misc

-   [#2245](https://github.com/pulp/pulp_rpm/issues/2245), [#2276](https://github.com/pulp/pulp_rpm/issues/2276), [#2302](https://github.com/pulp/pulp_rpm/issues/2302), [#2560](https://github.com/pulp/pulp_rpm/issues/2560), [#2565](https://github.com/pulp/pulp_rpm/issues/2565), [#2599](https://github.com/pulp/pulp_rpm/issues/2599), [#2620](https://github.com/pulp/pulp_rpm/issues/2620)

---

## 3.17.22 (2024-02-09) {: #3.17.22 }

No significant changes.

---

## 3.17.21 (2024-02-09) {: #3.17.21 }

### Bugfixes

-   Taught RPM how to handle duplicate-advisory-ids at repository-version-create time.
    [#2821](https://github.com/pulp/pulp_rpm/issues/2821)
-   Addressed some edge-cases involving advisory-collection-naming and imports.
    [#3380](https://github.com/pulp/pulp_rpm/issues/3380)

---

## 3.17.20 (2023-10-13) {: #3.17.20 }

### Bugfixes

-   Improved performance by reducing the number of small queries during exports.
    [#3286](https://github.com/pulp/pulp_rpm/issues/3286)

---

## 3.17.19 (2023-10-02) {: #3.17.19 }

### Bugfixes

-   Fixed a deadlock during concurrent syncs of rpm-repos that need data fixups.
    [#2980](https://github.com/pulp/pulp_rpm/issues/2980)
-   Improved performance of exports significantly in some circumstances by optimizing a query.
    [#3259](https://github.com/pulp/pulp_rpm/issues/3259)

---

## 3.17.18 (2023-05-16) {: #3.17.18 }

### Bugfixes

-   Fixed concurrent-overlapping-sync of subrepos by making them repository-unique.

    This change is transparent to end-users.
    [#2278](https://github.com/pulp/pulp_rpm/issues/2278)

---

## 3.17.17 (2023-04-10) {: #3.17.17 }

### Bugfixes

-   Fix import/export not importing modulemd_packages data with ManyToMany relationship.
    [#3019](https://github.com/pulp/pulp_rpm/issues/3019)

---

## 3.17.16 (2023-02-16) {: #3.17.16 }

### Bugfixes

-   Allow syncing repos with a compressed comps.xml "group" metadata declared in repomd.xml.
    [#2753](https://github.com/pulp/pulp_rpm/issues/2753)

---

## 3.17.15 (2022-11-21) {: #3.17.15 }

### Bugfixes

-   Fix syncing repos with missing epoch metadata for packages.
    [#2858](https://github.com/pulp/pulp_rpm/issues/2858)
-   Fix an issue where the public key (repomd.xml.key) files generated by Pulp would be empty.
    [#2892](https://github.com/pulp/pulp_rpm/issues/2892)

---

## 3.17.14 (2022-10-19) {: #3.17.14 }

### Bugfixes

-   Deduplicate file entries
    [#2719](https://github.com/pulp/pulp_rpm/issues/2719)

### Misc

-   [#2791](https://github.com/pulp/pulp_rpm/issues/2791), [#2832](https://github.com/pulp/pulp_rpm/issues/2832)

---

## 3.17.13 (2022-09-27) {: #3.17.13 }

### Bugfixes

-   Perform a data repair during the sync process to address a couple of data quality issues. Namely: fix changelogs in some cases where what is saved no longer matches what is synced, and fix packages which were previously incorrectly marked as non-modular.
    [#2643](https://github.com/pulp/pulp_rpm/issues/2643)
-   Fix import/export of Alma linux repositories.
    [#2648](https://github.com/pulp/pulp_rpm/issues/2648)
-   Do not optimize sync if retain-package-versions was set/changed
    [#2704](https://github.com/pulp/pulp_rpm/issues/2704)
-   Fixed a bug were some SLES repos were publishing metadata with missing drpms.
    [#2705](https://github.com/pulp/pulp_rpm/issues/2705)
-   Fixed orphan cleanup error in case Addon(Variant) were pointing to same subrepo.
    [#2733](https://github.com/pulp/pulp_rpm/issues/2733)
-   Ensured unsupported metadata files are also handled during publish.
    [#2795](https://github.com/pulp/pulp_rpm/issues/2795)

### Misc

-   [#2620](https://github.com/pulp/pulp_rpm/issues/2620)

---

## 3.17.12 (2022-08-16) {: #3.17.12 }

No significant changes.

---

## 3.17.11 (2022-08-15) {: #3.17.11 }

No significant changes.

---

## 3.17.10 (2022-08-08) {: #3.17.10 }

### Bugfixes

-   Made sure that Pulp doesn't publish repos with duplicate NEVRA in some edge case scenarios.
    [#2407](https://github.com/pulp/pulp_rpm/issues/2407)
-   Allow syncing repositories with duplicate NEVRA in mirror_complete mode, but make sure syncing those packages are skipped.
    [#2691](https://github.com/pulp/pulp_rpm/issues/2691)

---

## 3.17.9 (2022-08-03) {: #3.17.9 }

### Bugfixes

-   Don't raise a fatal error when encountering mostly valid metadata that contains data we don't expect, or data in the wrong places, in situations where it doesn't really matter.
    [#2686](https://github.com/pulp/pulp_rpm/issues/2686)

---

## 3.17.8 (2022-08-01) {: #3.17.8 }

### Bugfixes

-   Improved error reporting in one scenario where it could be highly confusing.
    [#2395](https://github.com/pulp/pulp_rpm/issues/2395)
-   Fix package temporary upload path.
    [#2403](https://github.com/pulp/pulp_rpm/issues/2403)
-   Using retain_package_versions (with the required "additive" sync_policy) will now avoid downloading the older packages when synced with download_policy "on_demand", resulting in much faster and more efficient syncs.
    [#2479](https://github.com/pulp/pulp_rpm/issues/2479)
-   Improved error message for Alternate Content Source refresh when it has insufficient permissions.
    [#2667](https://github.com/pulp/pulp_rpm/issues/2667)

### Misc

-   [#2565](https://github.com/pulp/pulp_rpm/issues/2565)

---

## 3.17.7 (2022-07-05) {: #3.17.7 }

### Bugfixes

-   Fixed an issue that could cause orphan cleanup to fail for certain repos.
    [#2459](https://github.com/pulp/pulp_rpm/issues/2459)
-   Fixed unix timestamps not being parsed correctly for issued and updated dates.
    [#2528](https://github.com/pulp/pulp_rpm/issues/2528)
-   Fix a small FD leak during complete mirror syncs
    [#2624](https://github.com/pulp/pulp_rpm/issues/2624)

### Misc

-   [#2276](https://github.com/pulp/pulp_rpm/issues/2276)

---

## 3.17.6 (2022-06-21) {: #3.17.6 }

### Features

-   RPM metadata is now sorted by package name and version information, which slightly improves compression efficiency.
    [#2274](https://github.com/pulp/pulp_rpm/issues/2274)

### Bugfixes

-   Fixed treeinfo processing to handle some very old treeinfo formats.
    [#2243](https://github.com/pulp/pulp_rpm/issues/2243)

---

## 3.17.5 (2022-04-12) {: #3.17.5 }

### Bugfixes

-   Substantial improvements to the memory consumption of syncs, with a modest improvement in time required to sync.
    [#2296](https://github.com/pulp/pulp_rpm/issues/2296)
-   Taught advisory-conflict-resolution to handle just-EVR-differences in incoming advisory's
    package-list. This solves the case of repositories that update advisories to always have
    the newest versions of RPMs (looking at you, EPEL...).
    [#2422](https://github.com/pulp/pulp_rpm/issues/2422)
-   Fix ULN remote username and password fields which ought to have been write-only and hidden.
    [#2428](https://github.com/pulp/pulp_rpm/issues/2428)
-   Fix the behavior of gpgcheck and repo_gpgcheck options when specified on the repository.
    [#2430](https://github.com/pulp/pulp_rpm/issues/2430)
-   Fix an issue where package requirements containing an ampersand character in the name might have their data parsed incorrectly, and added a data repair script (pulpcore-manager rpm-datarepair 2460).
    [#2460](https://github.com/pulp/pulp_rpm/issues/2460)
-   Fixed instances of /tmp/ being used instead of the worker's working directory.
    [#2475](https://github.com/pulp/pulp_rpm/issues/2475)
-   Changed the naming of the trim_rpm_changelogs management command to rpm-trim-changelogs to better match with other command names.
    [#2488](https://github.com/pulp/pulp_rpm/issues/2488)

---

## 3.17.4 (2022-02-24) {: #3.17.4 }

### Bugfixes

-   Added an exception for a case where repository metadata is incorrect in such a way that it should not be "mirrored", and a warning in other cases. If these warnings / errors are encountered, the party which manages the repo should be contacted. If it is a public repo, an issue can be filed in our tracker, and we will follow up with that party following confirmation of the issue.
    [#2398](https://github.com/pulp/pulp_rpm/issues/2398)

---

## 3.17.3 (2022-01-29) {: #3.17.3 }

### Bugfixes

-   Fixed a Directory not empty error during publication creation. Usually observed on NFS and during pulp-2to3-migration but any publication creation can be affected.
    [#2379](https://github.com/pulp/pulp_rpm/issues/2379)

---

## 3.17.2 (2022-01-22) {: #3.17.2 }

### Features

-   Added a debug option for greater visibility into dependency solving.
    [#2343](https://github.com/pulp/pulp_rpm/issues/2343)

### Bugfixes

-   Fixed an edge case with the changelog limit.
    [#2363](https://github.com/pulp/pulp_rpm/issues/2363)
-   Fixed downloading from addon repositories provided as a part of a distribution/kickstart tree.
    [#2373](https://github.com/pulp/pulp_rpm/issues/2373)

### Misc

-   [#2361](https://github.com/pulp/pulp_rpm/issues/2361)

---

## 3.17.1 (2022-01-18) {: #3.17.1 }

### Bugfixes

-   Fixed a migration to be able to upgrade to pulp_rpm 3.17.
    [#2356](https://github.com/pulp/pulp_rpm/issues/2356)

---

## 3.17.0 (2022-01-17) {: #3.17.0 }

### Features

-   Added API to allow uploading of a comps.xml file.
    [#2313](https://github.com/pulp/pulp_rpm/issues/2313)
-   Added a per-package changelog entry limit with a default value of 10, which is controlled by a setting named KEEP_CHANGELOG_LIMIT. This only impacts the output of [dnf changelog $package]{.title-ref} - it is always possible to get the full list of changelogs using [rpm -qa --changelog $package]{.title-ref} if the package is installed on the system. This limit can yield very substantial savings time and resources for some repositories.
    [#2332](https://github.com/pulp/pulp_rpm/issues/2332)
-   Added support for Alternate Content Sources.
    [#2340](https://github.com/pulp/pulp_rpm/issues/2340)

### Bugfixes

-   Fixed distribution tree sync for repositories with partial .treeinfo (e.g. most of CentOS 8 repositories).
    [#2305](https://github.com/pulp/pulp_rpm/issues/2305)
-   Fixed a regression dealing with downloads of filenames containing special characters.
    Specifically, synching Amazon linux repositories with RPMs like uuid-c++.
    [#2315](https://github.com/pulp/pulp_rpm/issues/2315)
-   Fixed a bug that could result in incomplete repo metadata when "mirror_complete" sync policy is combined with the "optimize" option.
    [#2316](https://github.com/pulp/pulp_rpm/issues/2316)
-   Ensured that RPM plugin uses only a worker working directory and not /tmp which could have caused the out-of-disc-space issue since it's not expected that Pulp uses /tmp.
    [#2317](https://github.com/pulp/pulp_rpm/issues/2317)
-   In case that only a subtree is synced, it can happen that the PRIMARY_REPO key does not exists in repo_sync_results and the sync failed with accessing a not existing key at the end.
    [#2318](https://github.com/pulp/pulp_rpm/issues/2318)
-   Fixed sync of repositories using 'sha' as an alias for the sha1 checksum-type.
    [#2319](https://github.com/pulp/pulp_rpm/issues/2319)
-   Fixed FileNotFoundError during sync and Pulp 2 to Pulp 3 migration when a custom repo metadata has its checksum as a filename.
    [#2321](https://github.com/pulp/pulp_rpm/issues/2321)
-   Fix HTTP-proxy support for ULN-remotes
    [#2322](https://github.com/pulp/pulp_rpm/issues/2322)
-   Fixed file descriptor leak during repo metadata publish.
    [#2331](https://github.com/pulp/pulp_rpm/issues/2331)

### Improved Documentation

-   Expanded the documentation to include examples using pulp-cli.
    [#2314](https://github.com/pulp/pulp_rpm/issues/2314)

### Misc

-   [#2320](https://github.com/pulp/pulp_rpm/issues/2320), [#2323](https://github.com/pulp/pulp_rpm/issues/2323)

---

## 3.16.2 (2021-12-22) {: #3.16.2 }

### Bugfixes

-   Fixed sync of repositories using 'sha' as an alias for the sha1 checksum-type.
    (backported from #9580)
    [#9624](https://pulp.plan.io/issues/9624)
-   In case that only a subtree is synced, it can happen that the PRIMARY_REPO key does not exists in repo_sync_results and the sync failed with accessing a not existing key at the end.
    (backported from #9565)
    [#9628](https://pulp.plan.io/issues/9628)
-   Ensured that RPM plugin uses only a worker working directory and not /tmp which could have caused the out-of-disc-space issue since it's not expected that Pulp uses /tmp.
    (backported from #9551)
    [#9629](https://pulp.plan.io/issues/9629)
-   Fixed FileNotFoundError during sync and Pulp 2 to Pulp 3 migration when a custom repo metadata has its checksum as a filename.
    (backported from #9636)
    [#9650](https://pulp.plan.io/issues/9650)
-   Fix HTTP-proxy support for ULN-remotes
    (backported from #9647)
    [#9653](https://pulp.plan.io/issues/9653)

### Misc

-   [#9626](https://pulp.plan.io/issues/9626)

---

## 3.16.1 (2021-10-27) {: #3.16.1 }

### Bugfixes

-   Fixed a bug that could result in incomplete repo metadata when "mirror_complete" sync policy is combined with the "optimize" option.
    (backported from #9535)
    [#9536](https://pulp.plan.io/issues/9536)
-   Fixed a regression dealing with downloads of filenames containing special characters.
    Specifically, synching Amazon linux repositories with RPMs like uuid-c++.
    (backported from #9529)
    [#9537](https://pulp.plan.io/issues/9537)

---

## 3.16.0 (2021-10-20) {: #3.16.0 }

### Features

-   Added a sync_policy parameter to the /sync/ endpoint which will replace the mirror parameter and provides additional options and flexibility about how the sync should be carried out. The mirror parameter is now deprecated but for backwards compatibility it will remain present.
    [#9316](https://pulp.plan.io/issues/9316)
-   Make sync optimization less sensitive to remote changes which wouldn't have any impact on the sync outcomes, and fix some situations where the sync should not be skipped.
    [#9398](https://pulp.plan.io/issues/9398)

### Bugfixes

-   Fixed metadata generation after changing ALLOWED_CONTENT_CHECKSUMS.
    [#8571](https://pulp.plan.io/issues/8571)

-   For certain repos which use a rare feature of RPM metadata, "mirroring" would lead to a surprising / suboptimal result for most Pulp users. We now reject syncing these repos with mirroring enabled.
    [#9303](https://pulp.plan.io/issues/9303)

-   Fix an error that could occur when performing a non-mirror sync while using the skip_types option.
    [#9308](https://pulp.plan.io/issues/9308)

-   For certain repos which use a rare feature of RPM metadata, "mirroring" would lead to a broken repo. We now reject syncing these repos with mirroring enabled.
    [#9328](https://pulp.plan.io/issues/9328)

-   Fixes a regression in support for syncing from mirrorlists.
    [#9329](https://pulp.plan.io/issues/9329)

-   Fix an edge case where the repo gpg key URL would be calculated incorrectly if CONTENT_PREFIX was set to "/".
    [#9350](https://pulp.plan.io/issues/9350)

-   Vastly improved copy-with-depsolving performance.
    [#9387](https://pulp.plan.io/issues/9387)

-   For certain repos which use Delta RPMs (which Pulp 3 does not and will not support) we now reject syncing these repos with mirroring enabled to avoid confusing clients with unusable Delta metadata.
    [#9407](https://pulp.plan.io/issues/9407)

-   Generated .repo file now includes the "name" field.
    [#9438](https://pulp.plan.io/issues/9438)

-   Use checksum type of a package for publication if it's not configured.
    [#9448](https://pulp.plan.io/issues/9448)

-   Restored the functionality of specifying basic-auth parameters in a remote's URL.

    NOTE: it's much better to specify username/pwd explcitly on the Remote, rather
    than relying on embedding them in the URL. This fix will probably be deprecated in
    the future.
    [#9464](https://pulp.plan.io/issues/9464)

-   Fixed an issue where some repositories were unnecessarily prevented from using mirror-mode sync.
    [#9486](https://pulp.plan.io/issues/9486)

-   Disallowed adding simultaneously multiple advisories with the same id to a repo.
    Resolved the case when two or more advisories were already in a repo version.
    [#9503](https://pulp.plan.io/issues/9503)

### Improved Documentation

-   Added a note about scheduling tasks.
    [#9147](https://pulp.plan.io/issues/9147)

### Misc

-   [#9135](https://pulp.plan.io/issues/9135), [#9189](https://pulp.plan.io/issues/9189), [#9402](https://pulp.plan.io/issues/9402), [#9467](https://pulp.plan.io/issues/9467)

---

## 3.15.0 (2021-08-27) {: #3.15.0 }

### Features

-   Enable reclaim disk space for packages. This feature is available with pulpcore 3.15+.
    [#9176](https://pulp.plan.io/issues/9176)

### Bugfixes

-   Taught pulp_rpm to be more lenient in the face of non-standard repos.
    [#7208](https://pulp.plan.io/issues/7208)
-   Fixed multiple bugs in distribution tree metadata generation regarding "variant" and "variants" metadata.
    [#8622](https://pulp.plan.io/issues/8622)
-   Fixed Pulp 3 to Pulp 2 sync for the package groups with empty packagelist, e.g. RHEL8 Appstream repository.
    [#8713](https://pulp.plan.io/issues/8713)
-   Taught downloader to be handle rpms with special characters in ways Amazon likes.
    [#8875](https://pulp.plan.io/issues/8875)
-   Fixed some errors that can occur on occasions when identical content is being synced from multiple sources at once.
    [#9029](https://pulp.plan.io/issues/9029)
-   Comply with orphan clean up changes introduced in pulpcore 3.15
    [#9151](https://pulp.plan.io/issues/9151)
-   Unpublished content is no longer available for consumption.
    [#9223](https://pulp.plan.io/issues/9223)
-   Fixed an issue where mirror-mode syncs would not provide all of the files described in the .treeinfo metadata.
    [#9230](https://pulp.plan.io/issues/9230)
-   Taught copy-depsolving to behave better in a multiarch environment.
    [#9238](https://pulp.plan.io/issues/9238)
-   Fixed bug where sync tasks would open a lot of DB connections.
    [#9253](https://pulp.plan.io/issues/9253)
-   Improved the parallelism of copy operations.
    [#9255](https://pulp.plan.io/issues/9255)
-   Taught copy/ API to only do depsolving once when asked for.
    [#9287](https://pulp.plan.io/issues/9287)

### Deprecations and Removals

-   Dropped support for Python 3.6 and 3.7. pulp_rpm now supports Python 3.8+.
    [#9033](https://pulp.plan.io/issues/9033)

### Misc

-   [#8494](https://pulp.plan.io/issues/8494), [#9279](https://pulp.plan.io/issues/9279)

---

## 3.14.20 (2022-08-08) {: #3.14.20 }

### Bugfixes

-   Made sure that Pulp doesn't publish repos with duplicate NEVRA in some edge case scenarios.
    [#2407](https://github.com/pulp/pulp_rpm/issues/2407)
-   Allow syncing repositories with duplicate NEVRA in mirror_complete mode, but make sure syncing those packages are skipped.
    [#2691](https://github.com/pulp/pulp_rpm/issues/2691)

---

## 3.14.19 (2022-08-04) {: #3.14.19 }

### Bugfixes

-   Using retain_package_versions (with the required "additive" sync_policy) will now avoid downloading the older packages when synced with download_policy "on_demand", resulting in much faster and more efficient syncs.
    [#2479](https://github.com/pulp/pulp_rpm/issues/2479)

### Misc

-   [#2565](https://github.com/pulp/pulp_rpm/issues/2565)

---

## 3.14.18 (2022-08-03) {: #3.14.18 }

### Bugfixes

-   Don't raise a fatal error when encountering mostly valid metadata that contains data we don't expect, or data in the wrong places, in situations where it doesn't really matter.
    [#2686](https://github.com/pulp/pulp_rpm/issues/2686)

---

## 3.14.17 (2022-08-02) {: #3.14.17 }

### Bugfixes

-   Substantial improvements to the memory consumption of syncs, with a modest improvement in time required to sync.
    [#2296](https://github.com/pulp/pulp_rpm/issues/2296)
-   Improved error reporting in one scenario where it could be highly confusing.
    [#2395](https://github.com/pulp/pulp_rpm/issues/2395)

### Misc

-   [#2274](https://github.com/pulp/pulp_rpm/issues/2274)

---

## 3.14.16 (2022-07-08) {: #3.14.16 }

### Bugfixes

-   Fixed an issue that could cause orphan cleanup to fail for certain repos.
    [#2459](https://github.com/pulp/pulp_rpm/issues/2459)
-   Fix a small FD leak during complete mirror syncs
    [#2624](https://github.com/pulp/pulp_rpm/issues/2624)

### Misc

-   [#2276](https://github.com/pulp/pulp_rpm/issues/2276)

---

## 3.14.15 (2022-04-12) {: #3.14.15 }

### Bugfixes

-   Fix an issue where package requirements containing an ampersand character in the name might have their data parsed incorrectly, and added a data repair script (pulpcore-manager rpm-datarepair 2460).
    [#2460](https://github.com/pulp/pulp_rpm/issues/2460)
-   Fixed instances of /tmp/ being used instead of the worker's working directory.
    [#2475](https://github.com/pulp/pulp_rpm/issues/2475)

---

## 3.14.14 (2022-03-25) {: #3.14.14 }

### Bugfixes

-   Taught advisory-conflict-resolution to handle just-EVR-differences in incoming advisory's
    package-list. This solves the case of repositories that update advisories to always have
    the newest versions of RPMs (looking at you, EPEL...).
    [#2422](https://github.com/pulp/pulp_rpm/issues/2422)
-   Fix the behavior of gpgcheck and repo_gpgcheck options when specified on the repository.
    [#2430](https://github.com/pulp/pulp_rpm/issues/2430)

---

## 3.14.13 (2022-03-08) {: #3.14.13 }

### Bugfixes

-   Added an exception for a case where repository metadata is incorrect in such a way that it should not be "mirrored", and a warning in other cases. If these warnings / errors are encountered, the party which manages the repo should be contacted. If it is a public repo, an issue can be filed in our tracker, and we will follow up with that party following confirmation of the issue.
    [#2398](https://github.com/pulp/pulp_rpm/issues/2398)

---

## 3.14.12 (2022-01-29) {: #3.14.12 }

### Bugfixes

-   Fixed a Directory not empty error during publication creation. Usually observed on NFS and during pulp-2to3-migration but any publication creation can be affected.
    [#2379](https://github.com/pulp/pulp_rpm/issues/2379)

---

## 3.14.11 (2022-01-22) {: #3.14.11 }

### Bugfixes

-   Fixed an edge case with the changelog limit.
    [#2363](https://github.com/pulp/pulp_rpm/issues/2363)
-   Fixed downloading from addon repositories provided as a part of a distribution/kickstart tree.
    [#2373](https://github.com/pulp/pulp_rpm/issues/2373)

---

## 3.14.10 (2022-01-17) {: #3.14.10 }

### Bugfixes

-   Fixed distribution tree sync for repositories with partial .treeinfo (e.g. most of CentOS 8 repositories).
    [#2327](https://github.com/pulp/pulp_rpm/issues/2327)
-   Fixed file descriptor leak during repo metadata publish.
    (backported from #2331)
    [#2347](https://github.com/pulp/pulp_rpm/issues/2347)
-   Added a per-package changelog entry limit with a default value of 10, which is controlled by a setting named KEEP_CHANGELOG_LIMIT. This only impacts the output of [dnf changelog $package]{.title-ref} - it is always possible to get the full list of changelogs using [rpm -qa --changelog $package]{.title-ref} if the package is installed on the system. This limit can yield very substantial savings time and resources for some repositories.
    (backported from #2332)
    [#2348](https://github.com/pulp/pulp_rpm/issues/2348)

---

## 3.14.9 (2021-12-21) {: #3.14.9 }

### Bugfixes

-   Added a sync_policy parameter to the /sync/ endpoint which will replace the mirror parameter and provides options for how the sync should be carried out. The mirror parameter is deprecated but will retain its current function.
    (backported from #9316)
    [#9620](https://pulp.plan.io/issues/9620)
-   Fixed sync of repositories using 'sha' as an alias for the sha1 checksum-type.
    (backported from #9580)
    [#9625](https://pulp.plan.io/issues/9625)
-   Ensured that RPM plugin uses only a worker working directory and not /tmp which could have caused the out-of-disc-space issue since it's not expected that Pulp uses /tmp.
    (backported from #9551)
    [#9630](https://pulp.plan.io/issues/9630)
-   Fixed FileNotFoundError during sync and Pulp 2 to Pulp 3 migration when a custom repo metadata has its checksum as a filename.
    (backported from #9636)
    [#9649](https://pulp.plan.io/issues/9649)
-   Fix HTTP-proxy support for ULN-remotes
    (backported from #9647)
    [#9652](https://pulp.plan.io/issues/9652)

### Misc

-   [#9626](https://pulp.plan.io/issues/9626)

---

## 3.14.8 (2021-10-27) {: #3.14.8 }

### Bugfixes

-   Fixed a regression dealing with downloads of filenames containing special characters.
    Specifically, synching Amazon linux repositories with RPMs like uuid-c++.
    (backported from #9529)
    [#9541](https://pulp.plan.io/issues/9541)

---

## 3.14.7 (2021-10-18) {: #3.14.7 }

### Bugfixes

-   Disallowed adding simultaneously multiple advisories with the same id to a repo.
    Resolved the case when two or more advisories were already in a repo version.
    (backported from #9503)
    [#9519](https://pulp.plan.io/issues/9519)

---

## 3.14.6 (2021-10-05) {: #3.14.6 }

### Bugfixes

-   Fixed an issue where some repositories were unnecessarily prevented from using mirror-mode sync.
    (backported from #9486)
    [#9487](https://pulp.plan.io/issues/9487)

---

## 3.14.5 (2021-09-29) {: #3.14.5 }

### Bugfixes

-   Generated .repo file now includes the "name" field.
    (backported from #9438)
    [#9439](https://pulp.plan.io/issues/9439)

-   Use checksum type of a package for publication if it's not configured.

    (backported from #9448)
    [#9449](https://pulp.plan.io/issues/9449)

-   Restored the functionality of specifying basic-auth parameters in a remote's URL.

    NOTE: it's much better to specify username/pwd explcitly on the Remote, rather
    than relying on embedding them in the URL. This fix will probably be deprecated in
    the future.
    (backported from #9464)
    [#9472](https://pulp.plan.io/issues/9472)

### Misc

-   [#9437](https://pulp.plan.io/issues/9437)

---

## 3.14.4 (2021-09-22) {: #3.14.4 }

### Bugfixes

-   Fixed metadata generation after changing ALLOWED_CONTENT_CHECKSUMS.
    (backported from #8571)
    [#9332](https://pulp.plan.io/issues/9332)
-   Vastly improved copy-with-depsolving performance.
    (backported from #9387)
    [#9388](https://pulp.plan.io/issues/9388)
-   For certain repos which use a rare feature of RPM metadata, "mirroring" would lead to a broken repo. We now reject syncing these repos with mirroring enabled.
    (backported from #9328)
    [#9392](https://pulp.plan.io/issues/9392)
-   Fixes a regression in support for syncing from mirrorlists.
    (backported from #9329)
    [#9394](https://pulp.plan.io/issues/9394)
-   For certain repos which use Delta RPMs (which Pulp 3 does not and will not support) we now reject syncing these repos with mirroring enabled to avoid confusing clients with unusable Delta metadata.
    (backported from #9407)
    [#9408](https://pulp.plan.io/issues/9408)
-   Fix an edge case where the repo gpg key URL would be calculated incorrectly if CONTENT_PREFIX was set to "/".
    (backported from #9350)
    [#9429](https://pulp.plan.io/issues/9429)

---

## 3.14.3 (2021-08-31) {: #3.14.3 }

### Bugfixes

-   Taught copy-depsolving to behave better in a multiarch environment.
    (backported from #9238)
    [#9293](https://pulp.plan.io/issues/9293)
-   Taught copy/ API to only do depsolving once when asked for.
    (backported from #9287)
    [#9298](https://pulp.plan.io/issues/9298)
-   Fix an error that could occur when performing a non-mirror sync while using the skip_types option.
    (backported from #9308)
    [#9312](https://pulp.plan.io/issues/9312)
-   For certain repos which use a rare feature of RPM metadata, "mirroring" would lead to a surprising / suboptimal result for most Pulp users. We now reject syncing these repos with mirroring enabled.
    (backported from #9303)
    [#9315](https://pulp.plan.io/issues/9315)

### Misc

-   [#9318](https://pulp.plan.io/issues/9318)

---

## 3.14.2 (2021-08-24) {: #3.14.2 }

### Bugfixes

-   Fixed some errors that can occur on occasions when identical content is being synced from multiple sources at once.
    (backported from #9029)
    [#9267](https://pulp.plan.io/issues/9267)
-   Fixed an issue where mirror-mode syncs would not provide all of the files described in the .treeinfo metadata.
    (backported from #9230)
    [#9270](https://pulp.plan.io/issues/9270)

### Misc

-   [#9281](https://pulp.plan.io/issues/9281)

---

## 3.14.1 (2021-08-11) {: #3.14.1 }

### Bugfixes

-   Taught pulp_rpm to be more lenient in the face of non-standard repos.
    (backported from #7208)
    [#9192](https://pulp.plan.io/issues/9192)
-   Fixed Pulp 3 to Pulp 2 sync for the package groups with empty packagelist, e.g. RHEL8 Appstream repository.
    (backported from #8713)
    [#9193](https://pulp.plan.io/issues/9193)
-   Taught downloader to be handle rpms with special characters in ways Amazon likes.
    (backported from #8875)
    [#9198](https://pulp.plan.io/issues/9198)
-   Fixed multiple bugs in distribution tree metadata generation regarding "variant" and "variants" metadata.
    (backported from #8622)
    [#9218](https://pulp.plan.io/issues/9218)
-   Unpublished content is no longer available for consumption.
    (backported from #9223)
    [#9226](https://pulp.plan.io/issues/9226)

---

## 3.14.0 (2021-07-24) {: #3.14.0 }

### Bugfixes

-   Taught pulp_rpm how to deal with timestamp and filename oddities of SUSE repos.
    [#8275](https://pulp.plan.io/issues/8275)
-   Updated the signing service code to be compatible with pulpcore 3.10+.
    [#8608](https://pulp.plan.io/issues/8608)
-   Fixed inclusion by package group of an additional version of packages already selected to be copied
    [#9055](https://pulp.plan.io/issues/9055)
-   User proxy auth credentials of a Remote when syncing content.
    [#9064](https://pulp.plan.io/issues/9064)
-   Fixed server error when accessing /config.repo while using auto-distribute
    [#9071](https://pulp.plan.io/issues/9071)
-   Fixed a SUSE sync-error involving repomd-extra files with '-' in their filename.
    [#9096](https://pulp.plan.io/issues/9096)
-   Fix repository "mirroring" for repositories with Kickstart metadata / "Distribution Trees".
    [#9098](https://pulp.plan.io/issues/9098)
-   The fix for a previous issue resulting in incorrect metadata (#8995) was still regressing in some circumstances. Implemented a complete fix and added tests to ensure it never recurs.
    [#9107](https://pulp.plan.io/issues/9107)
-   Fixed an issue where mirrored syncs could fail if extra_files.json declared a checksum of a type that was disallowed in the Pulp settings.
    [#9111](https://pulp.plan.io/issues/9111)

### Misc

-   [#7891](https://pulp.plan.io/issues/7891), [#8972](https://pulp.plan.io/issues/8972)

---

## 3.13.3 (2021-07-07) {: #3.13.3 }

### Bugfixes

-   [#9023](https://pulp.plan.io/issues/9023)
-   Restored ability to correctly handle complicated mirrorlist URLs.
    (backported from #8981)
    [#9026](https://pulp.plan.io/issues/9026)
-   Fix UnboundLocalException if Pulp receives a non-404 HTTP error code when attempting to download metadata.
    (backported from #8787)
    [#9027](https://pulp.plan.io/issues/9027)

### Misc

-   [#7350](https://pulp.plan.io/issues/7350)

---

## 3.13.2 (2021-06-23) {: #3.13.2 }

### Bugfixes

-   Taught sync to process modulemd before packages so is_modular can be known.
    (backported from #8952)
    [#8964](https://pulp.plan.io/issues/8964)

---

## 3.13.1 (2021-06-23) {: #3.13.1 }

### Bugfixes

-   Fix filelists and changelogs not always being parsed correctly.
    (backported from #8955)
    [#8961](https://pulp.plan.io/issues/8961)
-   Fix an AssertionError that could occur when processing malformed (but technically valid) metadata.
    (backported from #8944)
    [#8962](https://pulp.plan.io/issues/8962)

---

## 3.13.0 (2021-06-17) {: #3.13.0 }

### Features

-   A sync with mirror=True will automatically create a publication using the existing metadata downloaded from the original repo, keeping the repository signature intact.
    [#6353](https://pulp.plan.io/issues/6353)
-   Allow the checksum types for packages and metadata to be unspecified, and intelligently decide which ones to use based on context if so.
    [#8722](https://pulp.plan.io/issues/8722)
-   Auto-publish no longer modifies distributions.
    Auto-distribute now only requires setting a distribution's `repository` field.
    [#8759](https://pulp.plan.io/issues/8759)
-   Substantially improved memory consumption while processing extremely large repositories.
    [#8864](https://pulp.plan.io/issues/8864)

### Bugfixes

-   Fixed publication of a distribution tree if productmd 1.33+ is installed.
    [#8807](https://pulp.plan.io/issues/8807)
-   Fixed sync for the case when SRPMs are asked to be skipped.
    [#8812](https://pulp.plan.io/issues/8812)
-   Allow static_context to be absent.
    [#8814](https://pulp.plan.io/issues/8814)
-   Fixed a trailing slash sometimes being inserted improperly if sles_auth_token is used.
    [#8816](https://pulp.plan.io/issues/8816)

### Misc

-   [#8681](https://pulp.plan.io/issues/8681)

---

## 3.12.0 (2021-05-19) {: #3.12.0 }

### Features

-   Add support for automatic publishing and distributing.
    [#7622](https://pulp.plan.io/issues/7622)
-   Added the ability to synchronize Oracle ULN repositories using ULN remotes.
    You can set an instance wide ULN server base URL using the DEFAULT_ULN_SERVER_BASE_URL setting.
    [#7905](https://pulp.plan.io/issues/7905)

### Bugfixes

-   Fixed advisory upload-and-merge of already-existing advisories.
    [#7282](https://pulp.plan.io/issues/7282)
-   Taught pulp_rpm to order resources on export to avoid deadlocking on import.
    [#7904](https://pulp.plan.io/issues/7904)
-   Reduce memory consumption when syncing extremely large repositories.
    [#8467](https://pulp.plan.io/issues/8467)
-   Fix error when updating a repository.
    [#8546](https://pulp.plan.io/issues/8546)
-   Fixed sync/migration of the kickstart repositories with floating point build_timestamp.
    [#8623](https://pulp.plan.io/issues/8623)
-   Fixed a bug where publication used the default metadata checksum type of SHA-256 rather than the one requested by the user.
    [#8644](https://pulp.plan.io/issues/8644)
-   Fixed advisory-upload so that a failure no longer breaks uploads forever.
    [#8683](https://pulp.plan.io/issues/8683)
-   Fixed syncing XZ-compressed modulemd metadata, e.g. CentOS Stream "AppStream"
    [#8700](https://pulp.plan.io/issues/8700)
-   Fixed a workflow where two identical advisories could 'look different' to Pulp.
    [#8716](https://pulp.plan.io/issues/8716)

### Improved Documentation

-   Added workflow documentation for the new ULN remotes.
    [#8426](https://pulp.plan.io/issues/8426)

### Misc

-   [#8509](https://pulp.plan.io/issues/8509), [#8616](https://pulp.plan.io/issues/8616), [#8764](https://pulp.plan.io/issues/8764)

---

## 3.11.4 (2022-01-29) {: #3.11.4 }

### Bugfixes

-   Fixed file descriptor leak during repo metadata publish.
    [#2331](https://github.com/pulp/pulp_rpm/issues/2331)
-   Fixed a Directory not empty error during publication creation. Usually observed on NFS and during pulp-2to3-migration but any publication creation can be affected.
    [#2379](https://github.com/pulp/pulp_rpm/issues/2379)

---

## 3.11.3 (2022-01-06) {: #3.11.3 }

### Bugfixes

-   Fixed FileNotFoundError during sync and Pulp 2 to Pulp 3 migration when a custom repo metadata has its checksum as a filename.
    (backported from #2321) [#2310](https://github.com/pulp/pulp_rpm/issues/2310)
-   Fixed distribution tree sync for repositories with partial .treeinfo (e.g. most of CentOS 8 repositories)
    [#2326](https://github.com/pulp/pulp_rpm/issues/2326)

---

## 3.11.2 (2021-08-24) {: #3.11.2 }

### Bugfixes

-   Taught pulp_rpm how to deal with timestamp and filename oddities of SUSE repos.
    (backported from #8275)
    [#9113](https://pulp.plan.io/issues/9113)
-   Fixed Pulp 3 to Pulp 2 sync for the package groups with empty packagelist, e.g. RHEL8 Appstream repository.
    (backported from #8713)
    [#9195](https://pulp.plan.io/issues/9195)
-   Taught pulp_rpm to be more lenient in the face of non-standard repos.
    (backported from #7208)
    [#9285](https://pulp.plan.io/issues/9285)

### Misc

-   [#9228](https://pulp.plan.io/issues/9228)

---

## 3.11.1 (2021-05-31) {: #3.11.1 }

### Bugfixes

-   Fixed sync for the case when SRPMs are asked to be skipped.
    (backported from #8812)
    [#8813](https://pulp.plan.io/issues/8813)
-   Allow static_context to be absent.
    (backported from #8814)
    [#8815](https://pulp.plan.io/issues/8815)

---

## 3.11.0 (2021-05-18) {: #3.11.0 }

### Features

-   Taught sync/copy/publish to recognize the new static_context attribute of modules.
    [#8638](https://pulp.plan.io/issues/8638)

### Bugfixes

-   Fixed syncing XZ-compressed modulemd metadata, e.g. CentOS Stream "AppStream"
    (backported from #8700)
    [#8751](https://pulp.plan.io/issues/8751)
-   Fixed a bug where publication used the default metadata checksum type of SHA-256 rather than the one requested by the user.
    (backported from #8644)
    [#8752](https://pulp.plan.io/issues/8752)
-   Reduce memory consumption when syncing extremely large repositories.
    (backported from #8467)
    [#8753](https://pulp.plan.io/issues/8753)

---

## 3.10.0 (2021-03-25) {: #3.10.0 }

### Features

-   Added the ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION configuration option.

    When set to True, overrides Pulp's advisory-merge logic regarding 'suspect'
    advisory collisions at sync and upload time and simply processes the advisory.
    [#8250](https://pulp.plan.io/issues/8250)

### Bugfixes

-   Taught pulp_rpm how to handle remotes whose URLs do not end in '/'.

    Specifically, some mirrors (e.g. Amazon2) return remotes like this.
    [#7995](https://pulp.plan.io/issues/7995)

-   Caught remaining places that needed to know that 'sha' is an alias for 'sha1'.

    Very old versions of createrepo used 'sha' as a checksum-type for 'sha-1'.
    The recent ALLOWED_CHECKSUMS work prevented repositories created this way
    from being synchronized or published.
    [#8052](https://pulp.plan.io/issues/8052)

-   Fixed DistributionTree parsing for boolean fields which could cause a failure at sync or migration time.
    [#8245](https://pulp.plan.io/issues/8245)

-   Taught advisory-conflict-resolution how to deal with another edge-case.
    [#8249](https://pulp.plan.io/issues/8249)

-   Fixed regression in advisory-upload when pkglist included in advisory JSON.
    [#8380](https://pulp.plan.io/issues/8380)

-   Fixed the case when no package checksum type cofiguration is provided for publications created outside, not by RPM plugin endpoints. E.g. in pulp-2to3-migration plugin.
    [#8422](https://pulp.plan.io/issues/8422)

### Misc

-   [#7537](https://pulp.plan.io/issues/7537), [#8223](https://pulp.plan.io/issues/8223), [#8278](https://pulp.plan.io/issues/8278), [#8301](https://pulp.plan.io/issues/8301), [#8392](https://pulp.plan.io/issues/8392)

---

## 3.9.1 (2021-03-11) {: #3.9.1 }

### Bugfixes

-   Fixed DistributionTree parsing for boolean fields which could cause a failure at sync or migration time.
    [#8374](https://pulp.plan.io/issues/8374)

---

## 3.9.0 (2021-02-04) {: #3.9.0 }

### Features

-   Make creation of sqlite metadata at Publication time an option, and default to false.
    [#7852](https://pulp.plan.io/issues/7852)
-   Check allowed checksum types when publish repository.
    [#7855](https://pulp.plan.io/issues/7855)

### Bugfixes

-   Fixed content serialization so it displays content checksums.
    [#8002](https://pulp.plan.io/issues/8002)
-   Fixing OpenAPI schema for on demand Distribution Trees
    [#8050](https://pulp.plan.io/issues/8050)
-   Fix a mistake in RPM copy that could lead to modules being copied when they should not be.
    [#8091](https://pulp.plan.io/issues/8091)
-   Fixed a mistake in dependency calculation code which could result in incorrect copy results and errors.
    [#8114](https://pulp.plan.io/issues/8114)
-   Fixed a bug that occurs when publishing advisories without an "updated" date set, which includes SUSE advisories.
    [#8162](https://pulp.plan.io/issues/8162)

### Improved Documentation

-   Fixed a mistake in the RPM copy workflow documentation.
    [#7978](https://pulp.plan.io/issues/7978)
-   Fixed a mistake in the copy API documentation - dependency solving was described as defaulting to OFF when in fact it defaults to ON.
    [#8009](https://pulp.plan.io/issues/8009)

### Misc

-   [#7843](https://pulp.plan.io/issues/7843)

---

## 3.8.0 (2020-11-12) {: #3.8.0 }

### Features

-   Added new fields allowing users to customize gpgcheck signature options in a publication.
    [#6926](https://pulp.plan.io/issues/6926)

### Bugfixes

-   Fixed re-syncing of custom repository metadata when it was the only change in a repository.
    [#7030](https://pulp.plan.io/issues/7030)
-   User should not be able to remove distribution trees, custom repository metadata and comps if they are used in repository.
    [#7431](https://pulp.plan.io/issues/7431)
-   Raise ValidationError when other type than JSON is provided during Advisory upload.
    [#7468](https://pulp.plan.io/issues/7468)
-   Added handling of HTTP 403 Forbidden during DistributionTree detection.
    [#7691](https://pulp.plan.io/issues/7691)
-   Fixed the case when downloads were happening outside of the task working directory during sync.
    [#7698](https://pulp.plan.io/issues/7698)

### Improved Documentation

-   Fixed broken documentation links.
    [#6981](https://pulp.plan.io/issues/6981)
-   Added documentation clarification around how checksum_types work during the Publication.
    [#7203](https://pulp.plan.io/issues/7203)
-   Added examples how to copy all content.
    [#7494](https://pulp.plan.io/issues/7494)
-   Clarified the advanced-copy section.
    [#7705](https://pulp.plan.io/issues/7705)

### Misc

-   [#7414](https://pulp.plan.io/issues/7414), [#7567](https://pulp.plan.io/issues/7567), [#7571](https://pulp.plan.io/issues/7571), [#7650](https://pulp.plan.io/issues/7650), [#7807](https://pulp.plan.io/issues/7807)

---

## 3.7.0 (2020-09-23) {: #3.7.0 }

### Bugfixes

-   Remove distribution tree subrepositories when a distribution tree is removed.
    [#7440](https://pulp.plan.io/issues/7440)
-   Avoid intensive queries taking place during the handling of the "copy" API web request.
    [#7483](https://pulp.plan.io/issues/7483)
-   Fixed "Value too long" error for the distribution tree sync.
    [#7498](https://pulp.plan.io/issues/7498)

### Misc

-   [#7040](https://pulp.plan.io/issues/7040), [#7422](https://pulp.plan.io/issues/7422), [#7519](https://pulp.plan.io/issues/7519)

---

## 3.6.3 (2020-11-19) {: #3.6.3 }

### Bugfixes

-   Fixed duplicate key error after incomplete sync task.
    [#7844](https://pulp.plan.io/issues/7844)

---

## 3.6.2 (2020-09-04) {: #3.6.2 }

### Bugfixes

-   Fixed a bug where dependency solving did not work correctly with packages that depend on files, e.g. depending on /usr/bin/bash.
    [#7202](https://pulp.plan.io/issues/7202)
-   Fixed crashes while copying SRPMs with depsolving enabled.
    [#7290](https://pulp.plan.io/issues/7290)
-   Fix sync using proxy server.
    [#7321](https://pulp.plan.io/issues/7321)
-   Fix sync from mirrorlist with comments (like fedora's mirrorlist).
    [#7354](https://pulp.plan.io/issues/7354)
-   Copying advisories/errata no longer fails if one of the packages is not present in the repository.
    [#7369](https://pulp.plan.io/issues/7369)
-   Fixing OpenAPI schema for Variant
    [#7394](https://pulp.plan.io/issues/7394)

---

## 3.6.1 (2020-08-20) {: #3.6.1 }

### Bugfixes

-   Updated Rest API docs to contain only rpm endpoints.
    [#7332](https://pulp.plan.io/issues/7332)
-   Fix sync from local (on-disk) repository.
    [#7342](https://pulp.plan.io/issues/7342)

### Improved Documentation

-   Fix copy script example typos.
    [#7176](https://pulp.plan.io/issues/7176)

---

## 3.6.0 (2020-08-17) {: #3.6.0 }

### Features

-   Taught advisory-merge to proactively avoid package-collection-name collisions.
    [#5740](https://pulp.plan.io/issues/5740)
-   Added the ability for users to import and export distribution trees.
    [#6739](https://pulp.plan.io/issues/6739)
-   Added import/export support for remaining advisory-related entities.
    [#6815](https://pulp.plan.io/issues/6815)
-   Allow a Remote to be associated with a Repository and automatically use it when syncing the
    Repository.
    [#7159](https://pulp.plan.io/issues/7159)
-   Improved publishing performance by around 40%.
    [#7289](https://pulp.plan.io/issues/7289)

### Bugfixes

-   Prevented advisory-merge from 'reusing' UpdateCollections from the merging advisories.
    [#7291](https://pulp.plan.io/issues/7291)

### Misc

-   [#6937](https://pulp.plan.io/issues/6937), [#7095](https://pulp.plan.io/issues/7095), [#7195](https://pulp.plan.io/issues/7195)

---

## 3.5.1 (2020-08-11) {: #3.5.1 }

### Bugfixes

-   Handle optimize=True and mirror=True on sync correctly.
    [#7228](https://pulp.plan.io/issues/7228)
-   Fix copy with depsolving for packageenvironments.
    [#7248](https://pulp.plan.io/issues/7248)
-   Taught copy that empty-content means 'copy nothing'.
    [#7284](https://pulp.plan.io/issues/7284)

---

## 3.5.0 (2020-07-24) {: #3.5.0 }

### Features

-   Add a retention policy feature - when specified, the latest N versions of each package will be kept and older versions will be purged.
    [#5367](https://pulp.plan.io/issues/5367)
-   Add support for comparing Packages by EVR (epoch, version, release).
    [#5402](https://pulp.plan.io/issues/5402)
-   Added support for syncing from a mirror list feed
    [#6225](https://pulp.plan.io/issues/6225)
-   Comps types (PackageCategory, PackageEnvironment, PackageGroup) can copy its children.
    [#6316](https://pulp.plan.io/issues/6316)
-   Added support for syncing Suse enterprise repositories with authentication token.
    [#6729](https://pulp.plan.io/issues/6729)

### Bugfixes

-   Fixed the sync issue for repositories with the same metadata files but different filenames. E.g. productid in RHEL8 BaseOS and Appstream.
    [#5847](https://pulp.plan.io/issues/5847)
-   Fixed an issue with an incorrect copy of a distribution tree.
    [#7046](https://pulp.plan.io/issues/7046)
-   Fixed a repository deletion when a distribution tree is a part of it.
    [#7096](https://pulp.plan.io/issues/7096)
-   Corrected several viewset-filters to be django-filter-2.3.0-compliant.
    [#7103](https://pulp.plan.io/issues/7103)
-   Allow only one distribution tree in a repo version at a time.
    [#7115](https://pulp.plan.io/issues/7115)
-   API is able to show modular data on advisory collection.
    [#7116](https://pulp.plan.io/issues/7116)

### Deprecations and Removals

-   Remove PackageGroup, PackageCategory and PackageEnvironment relations to packages and to each other.
    [#6410](https://pulp.plan.io/issues/6410)
-   Removed the query parameter relative_path from the API which was used when uploading an advisory
    [#6554](https://pulp.plan.io/issues/6554)

### Misc

-   [#7072](https://pulp.plan.io/issues/7072), [#7134](https://pulp.plan.io/issues/7134), [#7150](https://pulp.plan.io/issues/7150)

---

## 3.4.2 (2020-07-16) {: #3.4.2 }

### Bugfixes

-   Fixed CentOS 8 kickstart repository publications.
    [#6568](https://pulp.plan.io/issues/6568)
-   Updating API to not return publications that aren't complete.
    [#6974](https://pulp.plan.io/issues/6974)

### Improved Documentation

-   Change fixtures URL in the docs scripts.
    [#6656](https://pulp.plan.io/issues/6656)

### Misc

-   [#6778](https://pulp.plan.io/issues/6778)

---

## 3.4.1 (2020-06-03) {: #3.4.1 }

### Bugfixes

-   Including requirements.txt on MANIFEST.in
    [#6892](https://pulp.plan.io/issues/6892)

---

## 3.4.0 (2020-06-01) {: #3.4.0 }

### Features

-   Distributions now serves a config.repo, and when signing is enabled also a public.key, in the base_path.
    [#5356](https://pulp.plan.io/issues/5356)

### Bugfixes

-   Fixed the duplicated advisory case when only auxiliary fields were updated but not any timestamp or version.
    [#6604](https://pulp.plan.io/issues/6604)
-   Fixed dependency solving issue where not all RPM dependencies were coped.
    [#6820](https://pulp.plan.io/issues/6820)
-   Make 'last_sync_revision_number' nullable in all migrations.
    [#6861](https://pulp.plan.io/issues/6861)
-   Fixed a bug where the behavior of RPM advanced copy with dependency solving differed depending
    on the order of the source-destination repository pairs provided by the user.
    [#6868](https://pulp.plan.io/issues/6868)

### Improved Documentation

-   Added documentation for the RPM copy API.
    [#6332](https://pulp.plan.io/issues/6332)
-   Updated the required roles names
    [#6759](https://pulp.plan.io/issues/6759)

### Misc

-   [#4142](https://pulp.plan.io/issues/4142), [#6514](https://pulp.plan.io/issues/6514), [#6536](https://pulp.plan.io/issues/6536), [#6706](https://pulp.plan.io/issues/6706), [#6777](https://pulp.plan.io/issues/6777), [#6786](https://pulp.plan.io/issues/6786), [#6789](https://pulp.plan.io/issues/6789), [#6801](https://pulp.plan.io/issues/6801), [#6839](https://pulp.plan.io/issues/6839), [#6841](https://pulp.plan.io/issues/6841)

---

## 3.3.2 (2020-05-18) {: #3.3.2 }

### Bugfixes

-   Fix edge case where specifying 'dest_base_version' for an RPM copy did not work properly
    in all circumstances.
    [#6693](https://pulp.plan.io/issues/6693)
-   Add a new migration to ensure that 'last_sync_revision_number' is nullable.
    [#6743](https://pulp.plan.io/issues/6743)

---

## 3.3.1 (2020-05-07) {: #3.3.1 }

### Bugfixes

-   Taught copy to always include specified packages.
    [#6519](https://pulp.plan.io/issues/6519)
-   Fixed the upgrade issue, revision number can be empty now.
    [#6662](https://pulp.plan.io/issues/6662)

### Misc

-   [#6665](https://pulp.plan.io/issues/6665)

---

## 3.3.0 (2020-04-21) {: #3.3.0 }

### Features

-   Add dependency solving for modules and module-defaults.
    [#4162](https://pulp.plan.io/issues/4162)
-   Add dependency solving for RPMs.
    [#4761](https://pulp.plan.io/issues/4761)
-   Add incremental update -- copying an advisory also copies the RPMs that it references.
    [#4768](https://pulp.plan.io/issues/4768)
-   Enable users to publish a signed Yum repository
    [#4812](https://pulp.plan.io/issues/4812)
-   Add a criteria parameter to the copy api that can be used to filter content to by copied.
    [#6009](https://pulp.plan.io/issues/6009)
-   Added REST API for copying content between repositories.
    [#6018](https://pulp.plan.io/issues/6018)
-   Add a content parameter to the copy api that accepts a list of hrefs to be copied.
    [#6019](https://pulp.plan.io/issues/6019)
-   Functional test using bindings.
    [#6061](https://pulp.plan.io/issues/6061)
-   Added the field 'sha256' to the public API and enabled users to filter content by this field
    [#6187](https://pulp.plan.io/issues/6187)
-   Added a config param to copy api which maps multiple sources to destinations.
    [#6268](https://pulp.plan.io/issues/6268)
-   Default publish type is alphabetical directory structure under 'Packages' folder.
    [#4445](https://pulp.plan.io/issues/4445)
-   Enabled checksum selection when publishing metadata
    [#4458](https://pulp.plan.io/issues/4458)
-   Advisory version is considered at conflict resolution time.
    [#5739](https://pulp.plan.io/issues/5739)
-   Added support for opensuse advisories.
    [#5829](https://pulp.plan.io/issues/5829)
-   Optimize sync to only happen when there have been changes.
    [#6055](https://pulp.plan.io/issues/6055)
-   Store the checksum type (sum_type) for advisory packages as an integer, but continue displaying it to the user as a string. This brings the internal representation closer to createrepo_c which uses integers.
    [#6442](https://pulp.plan.io/issues/6442)
-   Add support for import/export processing
    [#6473](https://pulp.plan.io/issues/6473)

### Bugfixes

-   Fix sync for repositories with modular content.
    [#6229](https://pulp.plan.io/issues/6229)
-   Properly compare modular content between the versions.
    [#6303](https://pulp.plan.io/issues/6303)
-   Deserialize treeinfo files in a scpecific order
    [#6322](https://pulp.plan.io/issues/6322)
-   Fixed the repo revision comparison and sync optimization for sub-repos
    [#6367](https://pulp.plan.io/issues/6367)
-   Fixed repository metadata that was pointing to wrong file locations.
    [#6399](https://pulp.plan.io/issues/6399)
-   Fixed modular advisory publication.
    [#6440](https://pulp.plan.io/issues/6440)
-   Fixed advisory publication, missing auxiliary fields were added.
    [#6441](https://pulp.plan.io/issues/6441)
-   Fixed publishing of module repodata.
    [#6530](https://pulp.plan.io/issues/6530)

### Improved Documentation

-   Documented bindings installation for a dev environment
    [#6395](https://pulp.plan.io/issues/6395)

### Misc

-   [#5207](https://pulp.plan.io/issues/5207), [#5455](https://pulp.plan.io/issues/5455), [#6312](https://pulp.plan.io/issues/6312), [#6313](https://pulp.plan.io/issues/6313), [#6339](https://pulp.plan.io/issues/6339), [#6363](https://pulp.plan.io/issues/6363), [#6442](https://pulp.plan.io/issues/6442), [#6155](https://pulp.plan.io/issues/6155), [#6297](https://pulp.plan.io/issues/6297), [#6300](https://pulp.plan.io/issues/6300), [#6560](https://pulp.plan.io/issues/6560)

---

## 3.2.0 (2020-03-02) {: #3.2.0 }

### Features

-   Add mirror mode for sync endpoint.
    [#5738](https://pulp.plan.io/issues/5738)
-   Add some additional not equal filters.
    [#5854](https://pulp.plan.io/issues/5854)
-   SRPM can be skipped during the sync.
    [#6033](https://pulp.plan.io/issues/6033)

### Bugfixes

-   Fix absolute path error when parsing packages stored in S3
    [#5904](https://pulp.plan.io/issues/5904)
-   Fix advisory conflict resolution to check current version first.
    [#5924](https://pulp.plan.io/issues/5924)
-   Handling float timestamp on treeinfo file
    [#5989](https://pulp.plan.io/issues/5989)
-   Raise error when content has overlapping relative_path on the same version
    [#6152](https://pulp.plan.io/issues/6152)
-   Fixed an issue causing module and module-default metadata to be stored incorrectly, and added a data migration to fix existing installations.
    [#6191](https://pulp.plan.io/issues/6191)
-   Fix REST API for Modulemd "Package" list - instead of returning PKs, return Package HREFs as intended.
    [#6196](https://pulp.plan.io/issues/6196)
-   Replace RepositorySyncURL with RpmRepositorySyncURL
    [#6204](https://pulp.plan.io/issues/6204)
-   Modulemd dependencies are now stored corectly in DB.
    [#6214](https://pulp.plan.io/issues/6214)

### Improved Documentation

-   Remove the pulp_use_system_wide_pkgs installer variable from the docs. We now set it in the pulp_rpm_prerequisites role. Users can safely leave it in their installer variables for the foreseeable future though.
    [#5992](https://pulp.plan.io/issues/5992)

### Misc

-   [#6030](https://pulp.plan.io/issues/6030), [#6147](https://pulp.plan.io/issues/6147)

---

## 3.1.0 (2020-02-03) {: #3.1.0 }

### Features

-   Advisory now support reboot_suggested info.
    [#5737](https://pulp.plan.io/issues/5737)
-   Skip unsupported repodata.
    [#6034](https://pulp.plan.io/issues/6034)

### Misc

-   [#5867](https://pulp.plan.io/issues/5867), [#5900](https://pulp.plan.io/issues/5900)

---

## 3.0.0 (2019-12-12) {: #3.0.0 }

### Bugfixes

-   Providing a descriptive error message for RPM repos with invalid metadata
    [#4424](https://pulp.plan.io/issues/4424)
-   Improve memory performance on syncing.
    [#5688](https://pulp.plan.io/issues/5688)
-   Improve memory performance on publishing.
    [#5689](https://pulp.plan.io/issues/5689)
-   Resolve the issue which disallowed users to publish uploaded content
    [#5699](https://pulp.plan.io/issues/5699)
-   Provide a descriptive error for invalid treeinfo files
    [#5709](https://pulp.plan.io/issues/5709)
-   Properly handling syncing when there is no treeinfo file
    [#5732](https://pulp.plan.io/issues/5732)
-   Fix comps.xml publish: missing group attributes desc_by_lang, name_by_lang, and default now appear properly.
    [#5741](https://pulp.plan.io/issues/5741)
-   Fix error when adding/removing modules to/from a repository.
    [#5746](https://pulp.plan.io/issues/5746)
-   Splitting content between repo and sub-repo
    [#5761](https://pulp.plan.io/issues/5761)
-   Allow empty string for optional fields for comps.xml content.
    [#5856](https://pulp.plan.io/issues/5856)
-   Adds fields from the inherited serializer to comps.xml content types' displayed fields
    [#5857](https://pulp.plan.io/issues/5857)
-   Assuring uniqueness on publishing.
    [#5861](https://pulp.plan.io/issues/5861)

### Improved Documentation

-   Document that sync must complete before kicking off a publish
    [#5006](https://pulp.plan.io/issues/5006)
-   Add requirements to docs.
    [#5228](https://pulp.plan.io/issues/5228)
-   Update installation docs to use system-wide-packages.
    [#5564](https://pulp.plan.io/issues/5564)
-   Remove one shot uploader references and info.
    [#5747](https://pulp.plan.io/issues/5747)
-   Add 'Rest API' to menu.
    [#5749](https://pulp.plan.io/issues/5749)
-   Refactor workflow commands to small scripts.
    [#5750](https://pulp.plan.io/issues/5750)
-   Rename 'Errata' to 'Advisory' for consistency.
    [#5751](https://pulp.plan.io/issues/5751)
-   Update docs to include modularity and comps support to features.
    Include core-provided browseable distributions in features.
    [#5752](https://pulp.plan.io/issues/5752)
-   Update docs to include Tech Preview section
    [#5753](https://pulp.plan.io/issues/5753)
-   Update Quickstart page
    [#5754](https://pulp.plan.io/issues/5754)
-   Rearrange installation page and add missing information
    [#5755](https://pulp.plan.io/issues/5755)
-   Rearrange workflows section to have individual menu items for each content type.
    [#5758](https://pulp.plan.io/issues/5758)
-   Add content type descriptions and their specifics.
    [#5759](https://pulp.plan.io/issues/5759)
-   Document python build dependencies that must be installed on CentOS / RHEL.
    [#5841](https://pulp.plan.io/issues/5841)

### Misc

-   [#5325](https://pulp.plan.io/issues/5325), [#5693](https://pulp.plan.io/issues/5693), [#5701](https://pulp.plan.io/issues/5701), [#5757](https://pulp.plan.io/issues/5757), [#5853](https://pulp.plan.io/issues/5853)

---

## 3.0.0rc1 (2019-11-19)

### Features

-   Support for advisory upload.
    [#4012](https://pulp.plan.io/issues/4012)

-   Ensure there are no advisories with the same id in a repo version.

    In case where there are two advisories with the same id, either
    one of them is chosen, or they are merged, or there is an error raised
    if there is no way to resolve advisory conflict.
    [#4295](https://pulp.plan.io/issues/4295)

-   No duplicated content can be present in a repository version.
    [#4898](https://pulp.plan.io/issues/4898)

-   Added sync and publish support for comps.xml types.
    [#5495](https://pulp.plan.io/issues/5495)

-   Add/remove RPMs when a repo's modulemd gets added/removed
    [#5526](https://pulp.plan.io/issues/5526)

-   Make repositories "typed". Repositories now live at a detail endpoint. Sync is performed by POSTing to {repo_href}/sync/ remote={remote_href}.
    [#5625](https://pulp.plan.io/issues/5625)

-   Adding sub_repo field to RpmRepository
    [#5627](https://pulp.plan.io/issues/5627)

### Bugfixes

-   Fix publication for sub repos
    [#5630](https://pulp.plan.io/issues/5630)
-   Fix ruby bindings for UpdateRecord.
    [#5650](https://pulp.plan.io/issues/5650)
-   Fix sync of a repo which contains modules and advisories.
    [#5652](https://pulp.plan.io/issues/5652)
-   Fix 404 when repo remote URL is without trailing slash.
    [#5655](https://pulp.plan.io/issues/5655)
-   Check that sections exist before parsing them.
    [#5669](https://pulp.plan.io/issues/5669)
-   Stopping to save JSONFields as String.
    [#5671](https://pulp.plan.io/issues/5671)
-   Handling missing trailing slashes on kickstart tree fetching
    [#5677](https://pulp.plan.io/issues/5677)
-   Not require ref_id and title for UpdateReference
    [#5692](https://pulp.plan.io/issues/5692)
-   Refactor treeinfo handling and fix publication for kickstarts
    [#5729](https://pulp.plan.io/issues/5729)

### Deprecations and Removals

-   Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

    Creating / listing / editing / deleting RPM repositories is now performed on /pulp/api/v3/rpm/rpm/ instead of /pulp/api/v3/repositories/. Only RPM content can be present in a RPM repository, and only a RPM repository can hold RPM content.
    [#5625](https://pulp.plan.io/issues/5625)

-   Remove plugin managed repos
    [#5627](https://pulp.plan.io/issues/5627)

-   Rename endpoints for content to be in plural form consistently

    Endpoints removed -> added:

    /pulp/api/v3/content/rpm/modulemd/ -> /pulp/api/v3/content/rpm/modulemds/
    /pulp/api/v3/content/rpm/packagecategory/ -> /pulp/api/v3/content/rpm/packagecategories/
    /pulp/api/v3/content/rpm/packageenvironment/ -> /pulp/api/v3/content/rpm/packageenvironments/
    /pulp/api/v3/content/rpm/packagegroup/ -> /pulp/api/v3/content/rpm/packagegroups/
    [#5679](https://pulp.plan.io/issues/5679)

-   Rename module-defaults content endpoint for consistency

    Endpoints removed -> added:

    /pulp/api/v3/content/rpm/modulemd-defaults/ -> /pulp/api/v3/content/rpm/modulemd_defaults/
    [#5680](https://pulp.plan.io/issues/5680)

-   Remove /pulp/api/v3/rpm/copy/ endpoint

    Removed the /pulp/api/v3/rpm/copy/ endpoint. To copy all content now with typed repos, use the
    modify endpoint on a repository.
    [#5681](https://pulp.plan.io/issues/5681)

### Misc

-   [#3308](https://pulp.plan.io/issues/3308), [#4295](https://pulp.plan.io/issues/4295), [#5423](https://pulp.plan.io/issues/5423), [#5461](https://pulp.plan.io/issues/5461), [#5495](https://pulp.plan.io/issues/5495), [#5506](https://pulp.plan.io/issues/5506), [#5580](https://pulp.plan.io/issues/5580), [#5611](https://pulp.plan.io/issues/5611), [#5663](https://pulp.plan.io/issues/5663), [#5672](https://pulp.plan.io/issues/5672), [#5684](https://pulp.plan.io/issues/5684)

---

## 3.0.0b7 (2019-10-16)

### Features

-   Convert all the TextFields which store JSON content into Django JSONFields.
    [#5215](https://pulp.plan.io/issues/5215)

### Improved Documentation

-   Change the prefix of Pulp services from pulp-* to pulpcore-*
    [#4554](https://pulp.plan.io/issues/4554)
-   Docs update to use pulp_use_system_wide_pkgs.
    [#5488](https://pulp.plan.io/issues/5488)

### Deprecations and Removals

-   Change _id, _created, _last_updated, _href to pulp_id, pulp_created, pulp_last_updated, pulp_href
    [#5457](https://pulp.plan.io/issues/5457)
-   Removing repository from Addon/Variant serializers.
    [#5516](https://pulp.plan.io/issues/5516)
-   Moved endpoints for distribution trees and repo metadata files to /pulp/api/v3/content/rpm/distribution_trees/ and /pulp/api/v3/content/rpm/repo_metadata_files/ respectively.
    [#5535](https://pulp.plan.io/issues/5535)
-   Remove "_" from _versions_href, _latest_version_href
    [#5548](https://pulp.plan.io/issues/5548)

---

## 3.0.0b6 (2019-09-30)

### Features

-   Add upload functionality to the rpm contents endpoints.
    [#5453](https://pulp.plan.io/issues/5453)
-   Synchronize and publish modular content.
    [#5493](https://pulp.plan.io/issues/5493)

### Bugfixes

-   Add url prefix to plugin custom urls.
    [#5330](https://pulp.plan.io/issues/5330)

### Deprecations and Removals

-   Removing pulp/api/v3/rpm/upload/
    [#5453](https://pulp.plan.io/issues/5453)

### Misc

-   [#5172](https://pulp.plan.io/issues/5172), [#5304](https://pulp.plan.io/issues/5304), [#5408](https://pulp.plan.io/issues/5408), [#5421](https://pulp.plan.io/issues/5421), [#5469](https://pulp.plan.io/issues/5469), [#5493](https://pulp.plan.io/issues/5493)

---

## 3.0.0b5 (2019-09-17)

### Features

-   Setting code on ProgressBar.
    [#5184](https://pulp.plan.io/issues/5184)
-   Sync and Publish kickstart trees.
    [#5206](https://pulp.plan.io/issues/5206)
-   Sync and Publish custom/unknown repository metadata.
    [#5432](https://pulp.plan.io/issues/5432)

### Bugfixes

-   Use the field relative_path instead of filename in the API calls while creating a content from an artifact
    [#4987](https://pulp.plan.io/issues/4987)
-   Fixing sync task failure.
    [#5285](https://pulp.plan.io/issues/5285)

### Misc

-   [#4681](https://pulp.plan.io/issues/4681), [#5201](https://pulp.plan.io/issues/5201), [#5202](https://pulp.plan.io/issues/5202), [#5331](https://pulp.plan.io/issues/5331), [#5430](https://pulp.plan.io/issues/5430), [#5431](https://pulp.plan.io/issues/5431), [#5438](https://pulp.plan.io/issues/5438)

---

## 3.0.0b4 (2019-07-03)

### Features

-   Add total counts to the sync progress report.
    [#4503](https://pulp.plan.io/issues/4503)
-   Greatly speed up publishing of a repository.
    [#4591](https://pulp.plan.io/issues/4591)
-   Add ability to copy content between repositories, content type(s) can be specified.
    [#4716](https://pulp.plan.io/issues/4716)
-   Renamed Errata/Update content to Advisory to better match the terminology of the RPM/DNF ecosystem.
    [#4902](https://pulp.plan.io/issues/4902)
-   Python bindings are now published nightly and with each release as
    [pulp-rpm-client](https://pypi.org/project/pulp-rpm-client/). Also Ruby bindings are published
    similarly to rubygems.org as [pulp_rpm_client](https://rubygems.org/gems/pulp_rpm_client).
    [#4960](https://pulp.plan.io/issues/4960)
-   Override the Remote's serializer to allow policy='on_demand' and policy='streamed'.
    [#5065](https://pulp.plan.io/issues/5065)

### Bugfixes

-   Require relative_path at the content unit creation time.
    [#4835](https://pulp.plan.io/issues/4835)
-   Fix migraitons failure by making models compatible with MariaDB.
    [#4909](https://pulp.plan.io/issues/4909)
-   Fix unique index length issue for MariaDB.
    [#4916](https://pulp.plan.io/issues/4916)

### Improved Documentation

-   Switch to using [towncrier](https://github.com/hawkowl/towncrier) for better release notes.
    [#4875](https://pulp.plan.io/issues/4875)
-   Add a docs page about the Python and Ruby bindings.
    [#4960](https://pulp.plan.io/issues/4960)

### Misc

-   [#4117](https://pulp.plan.io/issues/4117), [#4567](https://pulp.plan.io/issues/4567), [#4574](https://pulp.plan.io/issues/4574), [#5064](https://pulp.plan.io/issues/5064)
