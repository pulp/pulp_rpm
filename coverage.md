Functional Tests Coverage
=========================

This file contains list of features and their test coverage.

| Feature | Coverage | Notes |
|--|--|--|
| **Sync** |  |  |
| As a user, I can sync all yum content types ( NO drpm) with immediate policy | PART |  |
| As a user, I can sync all yum content types ( NO drpm) with on-demand policy | PART | only types contained in rpm-unsigned + kickstart fixture |
| As a user, I can sync all yum content types ( NO drpm) with cache-only policy | PART | only types contained in rpm-unsigned |
| As a user, I can sync all yum content types ( NO drpm) in a mirror mode | PART | only types contained in rpm-unsigned |
| As a user, I can sync all yum content types ( NO drpm) in additive mode (default) | PART | checking counts of packages and advisories |
| As a user, I can sync all yum content types ( NO drpm) with optimization in additive mode| PART
 | only types contained in rpm-unsigned |
  As a user, I can sync all yum content types ( NO drpm) with optimization in mirror mode| PART
   | only types contained in rpm-unsigned |
| As a user, my mirror-mode syncs are exactly identical to the upstream repo (checksums, metadata files, repomd signature, package locations, extra_files.json) | NO | Needs fixture https://pulp.plan.io/issues/8809 |
| As a user, I can sync an RPM repository from the local filesystem | PART | Only tested with basic fixture in immediate mode with mirroring enabled |
| As a user, I can sync and skip specific type (srpm) | YES |  |
| As a user, I can sync opensuse repository | NO |  |
| As a user, I can sync Oracle repository using ULN | NO | |
| As a user, I can sync from a mirror list | YES |  |
| As a user, I can sync from a mirror list with comments | YES |  |
| As a user, I can sync from CDN using certificates | YES |  |
| As a user, I can re-sync custom repository metadata when it was the only change in a repository | YES |  |
| As a user, I can sync an existing advisory whose dates are timestamps (as opposed to datetimes) | NO  | Example: https://updates.suse.com/SUSE/Updates/SLE-SERVER/12-SP5/x86_64/update/ |
| As a user, I can sync repos with repomd.xml files whose filenames contain dashes (e.g., app-icons.tar.gz) | NO  | Example: https://updates.suse.com/SUSE/Updates/SLE-SERVER/12-SP5/x86_64/update/ |
| As a user, the content metadata being saved to Pulp is correct | PART | Packages and distribution trees are covered. Updateinfo and Groups metadata is not covered. "Weird" cases not covered. |
| As a user, the metadata being produced by Pulp is correct | PART | Primary, Filelists, and Other metadata is covered, Distribution Tree (.treeinfo) metadata is covered, Updateinfo and Groups metadata is not covered. "Weird" cases not covered. |
| **Duplicates** |  |  |
| As a user, I have only one advisory with the same id in a repo version | YES |  |
| As a user, I have only one module with the same NSVCA in a repo version | NO |  |
| As a user, I have only one [S]RPM with the same NEVRA in a repo version | YES |  |
| As a user, I have only one distribution tree, custom metadata of a certain type in a repo version | NO |  |
| As a user, I have only one module-defaults, package groups, category or environment with the same name in a repo version. | NO |  |
| **Publish** |  |  |
| As a user, I can publish repodata with specific checksum type | PART | "on_demand is not covered, https://pulp.plan.io/issues/6503" |
| As a user, I have the published root directory containing the ‘Package’ directory and packages in alphabetical order inside it. | YES | testing with modularity and kickstarter repositories, contains test if no extra files are present |
| As a user, I can sign repository metadata using a signing service and publish such repo | PART |  |
| As a user, I can have a config.repo file generated for any distribution at runtime | YES |  |
| As a user I can set/update repo_gpgcheck and gpg_check options | YES | |
| As a user I can set/update option to publish sqlite metadata | YES | |
| **Upload** |  |  |
| As a user, I can upload rpm packages, advisories and modulemd[-defaults] content types and optionally add them to repository | NO |  |
| As a user, I can upload rpm packages, advisories and modulemd[-defaults] type of content in chunks | PART |  |
| **Copy** |  |  |
| As a user, I can copy any content by adding it to a repository with modify/ endpoint (but nothing is copied automatically, and invalid repositories will fail to validate for some definition of “invalid”) | NO |  |
| As a user, I can copy any content by href using Copy API | PART |  |
| As a user, I can copy RPM package and its dependencies (if depsolving=True) | YES | to empty and non-empty repository |
| As a user, I can copy Advisory and packages it refers to (and their dependencies if depsolving=True) by copying the Advisory | YES |  |
| As a user, I can copy PackageCategories, PackageEnvironments and PackageGroups (and their dependencies) | PART | no packageenvironment test |
| As a user, I can copy Modulemd and its artifacts by copying the Modulemd | NO |  |
| As a user, I can copy Modulemd with its artifacts and its module dependencies and artifacts’ dependencies (if depsolving=True). | NO |  |
| As a user, if the default Modulemd is copied, its module-default is copied as well (and vice-versa) | NO |  |
| As a user, I can copy content with dep solving on and specify multiple repositories to copy from/to | NO |  |
| As a user, all content that I directly specify to be copied should always be copied (obviously, but we need to test it, there have been dependency solving bugs where it didn’t happen for various reasons) | NO |  |
| Dependencies can be solved for RPM packages which depend on specific files (such as /usr/bin/bash) present only in filelists.xml | NO | needs a fixture change/improvement |
| **Remove** |  |  |
| As a user, when a module is removed, its packages are removed as well ( not referenced by other modules) | NO |  |
| As a user, I can't remove content when it is used in a repository | PART | covered list in test_crud_content |
| **Consumer cases** |  |  |
| As a user, I can use dnf to install all the content served by Pulp | PART | only covers rpm installation with DNF |
| **Retention** |  |  |
| As a user, I can have a repository option that retains the latest N packages of the same name | PART | No coverage of packages with differing arch in same repo (src, i686, x86_64), no coverage of non-sync repo modifications, no coverage of modular RPMs being exempted. |
| As a user, I can export RPM-repository content to be consumed by a downstream Pulp3 instance. | PART | basic pulp-export succeeds |
| As a user, I can import RPM-repository content exported from an upstream Pulp3 instance. | PART | basic pulp-import succeeds |
| As a user, I can export/import an RPM repository with a kickstart | PART | Need to use rpm-distribution-tree fixture and check content after import |
