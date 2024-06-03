# Modify Repository Content

Modyfing existing Repository Content lets you filter what content you want in a Repository.

Keep in mind that none of these operations introduces new Content or deletes a Content from a Pulp instance.
To populate Pulp, see [Post and Delete Content](site:pulp_rpm/docs/user/guides/02-upload/) or [Create, Sync and Publish a Repository](site:pulp_rpm/docs/user/tutorials/01-create_sync_publish/).

## Basic Repository Modification API

Like all Pulp repositories, you can use `pulp rpm repository modify` to:

- Add or remove individual content units from a repository by HREF.
- Clone a repository version using `base_version`. This enables roll-back to a previous version.
  
### Sample Setup

If you want to experiment with the operations on some sample data, run this setup so you can follow along.
The output is based on this sample and only makes sense if the operations are followed in order.

```bash
pulp rpm repository create --name modify_test_repo
pulp rpm repository create --name fixture_repo
pulp rpm remote create --name fixture_remote --url https://fixtures.pulpproject.org/rpm-unsigned/
pulp rpm repository sync --repository fixture_repo --remote fixture_remote
```

### Add content to Repository

1. Set required variables:
    * `REPONAME`: The repository where you want to add
    * `ADD_LIST`: A json list with the `package_href` constructed like:
    ```json
    [{"pulp_href": "/pulp/api/v3/content/rpm/packages/018ea4c6-50f2-7895-aaf9-d1dde2b94c20/"}]
    ```
2. Run the modify command
3. Inspect the created Repository Version

=== "Add Packages to a Repository"

    ```bash
    # Set required variables
    REPONAME=modify_test_repo
    ADD_LIST=$(pulp rpm repository content list \
        --repository fixture_repo \
        --limit 5 | jq -r '[.[] | {pulp_href}]')

    # Run the modify command
    pulp rpm repository content modify \
        --repository "${REPONAME}" \
        --add-content "${ADD_LIST}"
    
    # Inspect the Repository Version and its Contents
    pulp rpm repository show --name modify_test_repo | jq '.latest_version_href'
    pulp rpm repository content list --repository modify_test_repo | jq '.[].location_href'
    ```

=== "Output"

    ```json
    # last repository version. Now its 1, previous was 0
    "/pulp/api/v3/repositories/rpm/rpm/018ea4da-702b-7b20-b427-393efe196193/versions/1/"

    # last repository version content
    "zebra-0.1-2.noarch.rpm"
    "wolf-9.4-2.noarch.rpm"
    "whale-0.2-1.noarch.rpm"
    "walrus-5.21-1.noarch.rpm"
    "walrus-0.71-1.noarch.rpm"
    ```

### Remove content from a Repository

Removing a content means creating a new *Repository Version* that won't contain it anymore:

1. Set required variables:
    * `REPONAME`: The repository where you want to delete from
    * `REMOVE_LIST`: A json list with the `package_href` constructed like:
    ```json
    [{"pulp_href": "/pulp/api/v3/content/rpm/packages/018ea4c6-50f2-7895-aaf9-d1dde2b94c20/"}]
    ```
2. Run the modify command
3. Inspect the created Repository Version

=== "Remove Package from  a Repository"

    ```bash
    # Set required variables
    REPONAME=modify_test_repo
    REMOVE_LIST=$(pulp rpm repository content list \
        --repository modify_test_repo \
        --limit 2 | jq -r '[.[] | {pulp_href}]')

    # Run the modify command
    pulp rpm repository content modify \
        --repository "${REPONAME}" \
        --remove-content "${REMOVE_LIST}"
    
    # Inspect the Repository Version and its Contents
    pulp rpm repository show --name modify_test_repo | jq '.latest_version_href'
    pulp rpm repository content list --repository modify_test_repo | jq '.[].location_href'
    ```

=== "Output"

    ```json
    # last repository version. Now its 2, previous was 1
    "/pulp/api/v3/repositories/rpm/rpm/018ea4da-702b-7b20-b427-393efe196193/versions/2/"

    # last repository version content
    "whale-0.2-1.noarch.rpm"
    "walrus-5.21-1.noarch.rpm"
    "walrus-0.71-1.noarch.rpm"
    ```

### Copy content from a Repository Version

This operation will create a new *Repository Version* in the current Repository based on a previous version (that belongs to the same Repository).
It will contain the exact same contents as in the `base_version`, regardless of what content was previously present.

This can be combined with adding and removing content units in the same call.

1. Set required variables:
    * `REPONAME`: The repository to create a copy and get a `base_version` from.
    * `REPOVERSION`: The repository version number to roll-back to.
2. Run the modify command
3. Inspect the created Repository Version

=== "Clone a Repository Version"

    ```bash
    # Set required variables
    REPONAME=modify_test_repo
    REPOVERSION=1
    
    # Run the modify command
    pulp rpm repository content modify \
        --repository "${REPONAME}" \
        --base-version "${REPOVERSION}"

    # Inspect the Repository Version and its Contents
    pulp rpm repository show --name modify_test_repo | jq '.latest_version_href'
    pulp rpm repository content list --repository modify_test_repo | jq '.[].location_href'
    ```

=== "Output"

    ```json
    # last repository version. Now its 3, previous was 2
    "/pulp/api/v3/repositories/rpm/rpm/018ea4da-702b-7b20-b427-393efe196193/versions/3/"

    # last repository version content
    "zebra-0.1-2.noarch.rpm"
    "wolf-9.4-2.noarch.rpm"
    "whale-0.2-1.noarch.rpm"
    "walrus-5.21-1.noarch.rpm"
    "walrus-0.71-1.noarch.rpm"
    ```


## Advanced copy workflow

!!! note

    The RPM copy API is a **tech preview**, while we hope it can remain stable, it may be subject
    to change in future releases.


RPM repositories have a large number of unique use cases for which the standard 'generic' Pulp
repository modification API is insufficient, so a separate RPM-specific API is provided for more
'advanced' use cases.

### Background

Several types of RPM content, such as Advisories (Errata), Package Groups, and Modules
depend on the existence of other content units to be "correct" or meaningful. For example:

1. An Advisory (Errata) references RPM Packages and Modules that are needed to address a
   particular bug or security concern. In order for the Advisory to be useful, these RPM packages
   or Modules should be present in the same repository - otherwise when a client tries to install
   them it will not be able to fully apply the Advisory fix.
2. A Package Group is a group of RPM packages. If the RPM packages that a Package Group contains
   are not present in the same repository, the Package Group is effectively "broken" and won't be
   possible to install correctly on a client system.
3. A Module consists of many RPM packages (similar to a Package Group). If the module is added to
   a repository while the packages that its RPMs depend on are not, it may not be possible to
   install the module on a client system.
4. A Module can depend on other modules. If those modules are not present in the RPM repo, the
   module will not be installable on a client system.
5. RPM Packages typically depend on other RPM packages. If a lone RPM package is added to a
   repository without its dependencies, it will potentially not be installable on a client system.

The advanced copy API exists primarily to address these use cases.

In contrast to the repository modification API, when a copy is performed using the RPM copy
API it is permitted to additionally copy content in the background which you, the user,
did not explicitly tell it to copy. For example:

- When copying an Advisory (Errata) from one repository to another, all of the RPM packages
  directly referenced by the Advisory will also be copied (however, see note below
  regarding "best effort" in copies).
- When copying RPM packages from one repository to another, if dependency-resolution is enabled
  then all of the RPM packages that those packages depend on are also be copied.

The goal is to be as easy to use as possible, while allowing for a "best effort" at maintaining
the "correctness" of the repository, as well as its dependencies if requested.

!!! note

    In all cases, copy engages in a "best effort" attempt to fulfill the requirement. This
    means that, in the event of the copy process being unable to find entities it believes
    are necessary for the copy operation, **it will continue to execute the copy**. This
    can happen for a variety of reasons (e.g., the source repositor(ies) don't contain all
    of the referenced/required content, or the copy-configuration is incomplete or otherwise
    incorrect). In these instances, missing entities are logged as WARNINGs - be sure to
    check the logs if the results of a copy are unexpected.


### Dependency solving

When copying RPM packages, advisories, or modules between repositories, it is useful to ensure
that all of the RPM dependencies they need to be "installable" on a client system are also present
in the destination-repository.

For example: if you want to add the "hexchat" RPM to a new repository, and you want to be able
to install it from that repository, the repository should also contain hexchat's dependencies
such as "libnotify" and "gtk3".

This applies to all RPM concepts that "contain" RPMs, such as Advisories (Errata), Modules, and
PackageGroups. With the RPM copy API, you are afforded the option to have all dependencies (and
the dependencies of those dependencies) copied for you automatically, if they do not already exist
in the destination repository. In Pulp 2, this feature was documented as "advanced copy";
the Pulp3 behavior matches the "recursive-conservative" option from Pulp2 (copies **latest missing**
dependencies)

Solving these complex dependency relationships can be quite expensive, but is often necessary for
correctness. It is **enabled by default**, but can be disabled by setting the "dependency_solving"
parameter to a value of `False` when making calls against the API. Note that if you do choose not
to use dependency-solving, (or if you configure it incorrectly), it is possible to create incomplete
repositories.

!!! note

    While the default value for the "dependency_solving" parameter is currently `True`, this
    default is potentially subject to change in the future - until such a time as this API is
    stabilized.


Dependency solving does have some restrictions to be aware of. The set of content contained by
all repositories used in a copy operation must be "dependency closed", which is to say that no
content in any repository may have a dependency which cannot be satisfied by any content present
in any of the other repositories involved in the copy operation.

For example, in CentOS 8, there are two primary repositories which are called "BaseOS" and
"AppStream". RPMs present in the "AppStream" repository frequently depend on RPMs which are
not present in "AppStream", but are present in "BaseOS", instead.

In order to copy RPMs from a Pulp-clone of the "AppStream" repository, you must perform a
"multi-repository copy" so that the dependencies can be properly resolved. Please see the
recipe section below for more details on how to do this.



### Recipes

These are examples of how the RPM copy API should be used. This code isn't intended to be runnable
as-is, but rather as a template for how the calls should be constructed.

Create a new repository version in "dest_repo" containing all content units which are present in
the "source_repo_version". This essentially copies all content from the "source_repo_version" into
the "dest_repo", while leaving the content that was previously in the repository untouched, unless
retain package policy is set on the "dest_repo"

```bash
POST /pulp/api/v3/rpm/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF"}
]
```

!!! note

    Retain package policy is set by `retain_package_versions` option.
    When set, it identifies the maximum number of versions of each package to keep; as new versions of
    packages are added by upload, sync, or copy, older versions of the same packages are automatically
    removed. A value of 0 means "unlimited" and will keep all versions of each package.


Create a new repository version in "dest_repo" containing the two "content" units specified by href,
which are present in the "source_repo_version".

```bash
POST /pulp/api/v3/rpm/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$RPM_HREF1, $ADVISORY_HREF1]}
]
dependency_solving=False
```

Create a new repository version in "dest_repo" containing the two "content" units specified by href,
which are present in the "source_repo_version". Instead of adding them to the content present in
the latest repository version present in "dest_repo", instead create a new version based upon
the version numbered "dest_base_version" in "dest_repo". These semantics are similar to how the
"base_version" parameter is used in the repository modification API.

```bash
POST /pulp/api/v3/rpm/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "dest_base_version": "$DEST_BASE_VERSION", "content": [$RPM_HREF1, $ADVISORY_HREF1]}
]
```

Create a new repository version in "dest_repo" containing the two "content" units specified by href,
as well as all of their RPM and Module dependencies, which are present in the "source_repo_version".

```bash
POST /pulp/api/v3/rpm/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$RPM_HREF1, $ADVISORY_HREF1]}
]
dependency_solving=True
```

"Multi-repository-copy", required when any of the repositories involved in the copy are not "dependency closed".

Each of the pairs of source and destination repositories will see the content units that were
specified copied as normal. However when one of the content units has a dependency which is not
present in the same repository, but is present in one of the other "source" repositories listed,
it may be copied between the repos configured in that pair.

In the following example, if \$RPM_HREF1 depends on a content unit which is only present in
\$SRC_REPO_VERS_HREF2 and is not present in either \$DEST_REPO_HREF or \$DEST_REPO_HREF2, then
it will be copied from \$SRC_REPO_VERS_HREF2 to \$DEST_REPO_HREF2, even though no content was
specified to be copied between those repositories.

```bash
POST /pulp/api/v3/rpm/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$RPM_HREF1, $ADVISORY_HREF1]},
    {"source_repo_version": "$SRC_REPO_VERS_HREF2", "dest_repo": "$DEST_REPO_HREF2", "content": []},
]
dependency_solving=True
```
