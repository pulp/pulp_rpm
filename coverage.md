Manual Coverage
===============

| Feature | Coverage | Notes |
|--|--|--|
| **Sync** |  |  |
| As a user, I can sync all yum content types ( NO drpm) with immediate policy | PART |  |
| As a user, I can sync all yum content types ( NO drpm) with on-demand policy | PART | only types contained in rpm-unsigned + kickstart fixture |
| As a user, I can sync all yum content types ( NO drpm) with cache-only policy | PART | only types contained in rpm-unsigned |
| As a user, I can sync all yum content types ( NO drpm) with optimization | PART | only types contained in rpm-unsigned |
| As a user, I can sync all yum content types ( NO drpm) in a mirror mode | NO |  |
| As a user, I can sync all yum content types ( NO drpm) in additive mode (default) | NO |  |
| As a user, I can sync and skip specific type (srpm) | NO |  |
| As a user, I can sync opensuse repository | NO |  |
| As a user, I can sync from a mirror list | NO | not merged yet |
| **Duplicates** |  |  |
| As a user, I have only one advisory with the same id in a repo version | PART | https://pulp.plan.io/issues/6604 |
| As a user, I have only one module with the same NSVCA in a repo version | NO |  |
| As a user, I have only one [S]RPM with the same NEVRA in a repo version | YES |  |
| As a user, I have only one distribution tree, custom metadata of a certain type in a repo version | NO |  |
| As a user, I have only one module-defaults, package groups, category or environment with the same name in a repo version. | NO |  |
| **Publish** |  |  |
| As a user, I can publish repodata with specific checksum type | PART | "on_demand is not covered, https://pulp.plan.io/issues/6503" |
| As a user, I have the published root directory containing the ‘Package’ directory and packages in alphabetical order inside it. | NO | including that there is NO files which are not expected to be there |
| As a user, I can sign repository metadata using a signing service and publish such repo | PART |  |
| As a user, I can have a config.repo file generated for any distribution at runtime | YES |  |
| **Upload** |  |  |
| As a user, I can upload rpm packages, advisories and modulemd[-defaults] content types and optionally add them to repository | NO |  |
| As a user, I can upload rpm packages, advisories and modulemd[-defaults] type of content in chunks | PART |  |
| **Copy** |  |  |
| As a user, I can copy any content by adding it to a repository with modify/ endpoint (but nothing is copied automatically, and invalid repositories will fail to validate for some definition of “invalid”) | NO |  |
| As a user, I can copy any content by href using Copy API | PART |  |
| As a user, I can copy RPM package and its dependencies (if depsolving=True) | NO |  |
| As a user, I can copy Advisory and packages it refers to (and their dependencies if depsolving=True) by copying the Advisory | PART |  |
| As a user, I can copy Modulemd and its artifacts by copying the Modulemd | NO |  |
| As a user, I can copy Modulemd with its artifacts and its module dependencies and artifacts’ dependencies (if depsolving=True). | NO |  |
| As a user, if the default Modulemd is copied, its module-default is copied as well (and vice-versa) | NO |  |
| As a user, I can copy content with dep solving on and specify multiple repositories to copy from/to | NO |  |
| As a user, all content that I directly specify to be copied should always be copied (obviously, but we need to test it, there have been dependency solving bugs where it didn’t happen for various reasons) | NO |  |
| **Remove** |  |  |
| As a user, when a module is removed, its packages are removed as well ( not referenced by other modules) | NO |  |
| **Consumer cases** |  |  |
| As a user, I can use dnf to install all the content served by Pulp | PART | only covers rpm installation |
