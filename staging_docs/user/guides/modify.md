# Modify Repository Content

Modifying existing Repository Content lets you filter what content you want in a Repository.

Keep in mind that none of these operations introduces new Content or deletes a Content from a Pulp instance.
To populate Pulp, see [Post and Delete Content](site:pulp_rpm/docs/user/guides/02-upload/) or [Create, Sync and Publish a Repository](site:pulp_rpm/docs/user/tutorials/01-create_sync_publish/).

## Basic Repository Modification API

Like all Pulp repositories, you can use `pulp rpm repository modify` to:

- Add or remove individual content units from a repository by HREF.
- Clone a repository version using `base_version`. This enables roll-back to a previous version.

### Sample Setup

If you want to experiment with the operations on some sample data, run this setup so you can follow along.
The output is based on this sample and only makes sense if the operations are followed in order.

=== "Setup"

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

1. Sets required variables:
    * `REPONAME`: The repository to create a copy and get a `base_version` from.
    * `REPOVERSION`: The repository version number to roll-back to.
2. Runs the modify command
3. Inspects the created Repository Version

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

!!! note

    If a destination repository has a retain-packages policy set, it will take effect after the copy.
    Retain package policy is set by `retain_package_versions` option.
    When set, it identifies the maximum number of versions of each package to keep; as new versions of
    packages are added by upload, sync, or copy, older versions of the same packages are automatically
    removed. A value of 0 means "unlimited" and will keep all versions of each package.

### Recipes

These are examples of how the RPM copy API should be used. This code isn't intended to be runnable
as-is, but rather as a template for how the calls should be constructed.

=== "Setup"

    ```bash
    export BASE_NAME="test_advanced_copy"
    # Create one remote
    pulp rpm remote create --name "${BASE_NAME}" --url "https://fixtures.pulpproject.org/rpm-signed/" --policy on_demand
    # Create 2 src and 2 dest repos
    for pre in "src" "dst"; do
      for inst in {1..2}; do
        echo "${pre}/${inst}"
        pulp rpm repository create --name "${pre}_${BASE_NAME}_${inst}" --remote "${BASE_NAME}" --no-autopublish
      done
    done
    # sync the src repos (only)
    for inst in {1..2}; do
      echo "SYNC src_${BASE_NAME}_${inst}}"
      pulp rpm repository sync --repository "src_${BASE_NAME}_${inst}"
    done
    # Find and remember one RPM HREF and one Advisory HREF from src1
    export rpm_href="$(pulp rpm content -t package list --name bear --version 4.1 --release 1 --field pulp_href | jq '.[0].pulp_href')"
    echo "RPM ${rpm_href}"
    export advisory_href="$(pulp rpm content -t advisory list --id RHEA-2012:0055 --field pulp_href | jq '.[0].pulp_href')"
    echo "ADVISORY ${advisory_href}"
    ```

#### Full repository copy

Create a new repository version in a destination repository containing all content units which are present in
the source repository-version. This essentially copies all content from the source version into
the destination repository.

=== "Copy All From Source To Destination"

    ```bash
    cat << EOF >  ./copy_test.json
    [
      {
        "source_repo_version": $(pulp rpm repository show --name "src_${BASE_NAME}_1" | jq '.latest_version_href'),
        "dest_repo": $(pulp rpm repository show --name "dst_${BASE_NAME}_1" | jq '.pulp_href')
      }
    ]
    EOF
    pulp rpm copy --config @./copy_test.json
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/01903bb0-34a1-7c58-82a8-30626adeec74/",
      "pulp_created": "2024-06-21T16:45:21.953880Z",
      "pulp_last_updated": "2024-06-21T16:45:21.953892Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.copy.copy_content",
      "logging_cid": "4bfd43b974ed46a58c70bb1df73c125d",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-06-21T16:45:21.972269Z",
      "started_at": "2024-06-21T16:45:22.026509Z",
      "finished_at": "2024-06-21T16:45:22.609179Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/01902cd4-50cc-79d3-bc8d-d4726981e072/",
      "parent_task": null,
      "child_tasks": [],
      "task_group": null,
      "progress_reports": [],
      "created_resources": [
        "/pulp/api/v3/repositories/rpm/rpm/01903baf-df99-7497-b9c4-fc882ebae05e/versions/1/"
      ],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:01903baf-df99-7497-b9c4-fc882ebae05e",
        "shared:prn:rpm.rpmrepository:01903baf-d818-765e-8cba-72e027fddda1",
        "shared:prn:core.domain:01902cd3-9252-72fe-9069-58fc3086c0cf"
      ]
    }
    ```

#### Specific-content copy

Create a new repository version in the destination repository containing the two content-units specified by href,
which are present in the source-repository.

=== "Copy Specific Content From Source To Destination"

    ```bash
    cat << EOF >  ./copy_test.json
    [
     {
       "source_repo_version": $(pulp rpm repository show --name "src_${BASE_NAME}_1" | jq '.latest_version_href'),
       "dest_repo": $(pulp rpm repository show --name "dst_${BASE_NAME}_1" | jq '.pulp_href'),
       "content": [${rpm_href}, ${advisory_href}]
     }
    ]
    EOF
    pulp rpm copy --config @./copy_test.json
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/01903bb1-ac68-7110-ae36-0a6079c17df6/",
      "pulp_created": "2024-06-21T16:46:58.152804Z",
      "pulp_last_updated": "2024-06-21T16:46:58.152815Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.copy.copy_content",
      "logging_cid": "8ac95a20fc27489cba22ca32e041ff70",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-06-21T16:46:58.182745Z",
      "started_at": "2024-06-21T16:46:58.233618Z",
      "finished_at": "2024-06-21T16:46:58.386792Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/01902cd4-53d3-705a-a316-c5d08dcebaaa/",
      "parent_task": null,
      "child_tasks": [],
      "task_group": null,
      "progress_reports": [],
      "created_resources": [],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:01903baf-df99-7497-b9c4-fc882ebae05e",
        "shared:prn:rpm.rpmrepository:01903baf-d818-765e-8cba-72e027fddda1",
        "shared:prn:core.domain:01902cd3-9252-72fe-9069-58fc3086c0cf"
      ]
    }
    ```

#### Specific-content to specific-destination-version copy

Create a new repository version in the destination repository containing the two content-units specified by href,
which are present in the source repository version. Instead of adding them to the content present in
the **latest** repository version present in destination repository, instead create a new version based upon
specified version-number of the destination repository. These semantics are similar to how the
`base_version` parameter is used in the repository modification API.

=== "Copy content to dest-repo/versions/0/"

    ```bash
    cat << EOF >  ./copy_test.json
    [
      {
        "source_repo_version": $(pulp rpm repository show --name "src_${BASE_NAME}_1" | jq '.latest_version_href'),
        "dest_repo": $(pulp rpm repository show --name "dst_${BASE_NAME}_1" | jq '.pulp_href'),
        "dest_base_version": 0,
        "content": [${rpm_href}, ${advisory_href}]
      }
    ]
    EOF
    pulp rpm copy --config @./copy_test.json
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/01903bb2-f7dc-7697-b33e-5a2f66ab58e8/",
      "pulp_created": "2024-06-21T16:48:23.004932Z",
      "pulp_last_updated": "2024-06-21T16:48:23.004944Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.copy.copy_content",
      "logging_cid": "f13911c4153f47348ccdc1e3dfea98e7",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-06-21T16:48:23.022271Z",
      "started_at": "2024-06-21T16:48:23.075167Z",
      "finished_at": "2024-06-21T16:48:23.235869Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/01902cd4-536f-7e31-aec9-059c55ba427c/",
      "parent_task": null,
      "child_tasks": [],
      "task_group": null,
      "progress_reports": [],
      "created_resources": [
        "/pulp/api/v3/repositories/rpm/rpm/01903baf-df99-7497-b9c4-fc882ebae05e/versions/2/"
      ],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:01903baf-df99-7497-b9c4-fc882ebae05e",
        "shared:prn:rpm.rpmrepository:01903baf-d818-765e-8cba-72e027fddda1",
        "shared:prn:core.domain:01902cd3-9252-72fe-9069-58fc3086c0cf"
      ]
    }
    ```

#### Copy content from src1 to dest1 **including dependencies**

Create a new repository version in the destination repository containing a specified content-unit,
as well as all of its RPM-dependencies, taken from the source repository-version.

=== "Copy specific content and dependencies from src to dest"

    ```bash
    cat << EOF >  ./copy_test.json
    [
      {
        "source_repo_version": $(pulp rpm repository show --name "src_${BASE_NAME}_1" | jq '.latest_version_href'),
        "dest_repo": $(pulp rpm repository show --name "dst_${BASE_NAME}_1" | jq '.pulp_href'),
        "content": [${advisory_href}]
      }
    ]
    EOF
    pulp rpm copy --config @./copy_test.json --dependency-solving
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/01903be8-1857-7cb8-a510-28096ede2771/",
      "pulp_created": "2024-06-21T17:46:24.727563Z",
      "pulp_last_updated": "2024-06-21T17:46:24.727574Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.copy.copy_content",
      "logging_cid": "a82707ece6d94ad48a9447569518df39",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-06-21T17:46:24.743962Z",
      "started_at": "2024-06-21T17:46:24.798102Z",
      "finished_at": "2024-06-21T17:46:24.965390Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/01902cd4-54c2-7d48-a74c-df41802bc946/",
      "parent_task": null,
      "child_tasks": [],
      "task_group": null,
      "progress_reports": [],
      "created_resources": [],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:01903baf-df99-7497-b9c4-fc882ebae05e",
        "shared:prn:rpm.rpmrepository:01903baf-d818-765e-8cba-72e027fddda1",
        "shared:prn:core.domain:01902cd3-9252-72fe-9069-58fc3086c0cf"
      ]
    }
    ```

#### Multi-repository copy

"Multi-repository-copy", required when any of the repositories involved in the copy are not "dependency closed".

Each of the pairs of source and destination repositories will see the content units that were
specified copied as normal. However when one of the content units has a dependency which is not
present in the same repository, but is present in one of the other "source" repositories listed,
it may be copied between the repos configured in that pair.

In the following example, if the specified RPM depends on a content unit which is only present in the second
source repository-version and is not present in either the first or second destination repository, then
it will be copied from the second source repository-version to the second destination repository, even though no
content was specified to be copied between those repositories.

=== "Copy content from src1/dest1 to src2/dest2"

    ```bash
    cat << EOF >  ./copy_test.json
    [
      {
        "source_repo_version": $(pulp rpm repository show --name "src_${BASE_NAME}_1" | jq '.latest_version_href'),
        "dest_repo": $(pulp rpm repository show --name "dst_${BASE_NAME}_1" | jq '.pulp_href'),
        "content": [${rpm_href}, ${advisory_href}]
      },
      {
        "source_repo_version": $(pulp rpm repository show --name "src_${BASE_NAME}_2" | jq '.latest_version_href'),
        "dest_repo": $(pulp rpm repository show --name "dst_${BASE_NAME}_2" | jq '.pulp_href'),
        "content": []
      }
    ]
    EOF
    pulp rpm copy --config @./copy_test.json --dependency-solving
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/01903be9-33e8-7b44-a43a-97b54dca3724/",
      "pulp_created": "2024-06-21T17:47:37.320871Z",
      "pulp_last_updated": "2024-06-21T17:47:37.320883Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.copy.copy_content",
      "logging_cid": "3b4553346d534751b37cc16aefed4975",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-06-21T17:47:37.335849Z",
      "started_at": "2024-06-21T17:47:37.392426Z",
      "finished_at": "2024-06-21T17:47:37.656981Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/01902cd4-5460-7186-ad57-c0eb34ddfe61/",
      "parent_task": null,
      "child_tasks": [],
      "task_group": null,
      "progress_reports": [],
      "created_resources": [],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:01903baf-df99-7497-b9c4-fc882ebae05e",
        "prn:rpm.rpmrepository:01903baf-e352-7b56-bffb-70f6afa479a9",
        "shared:prn:rpm.rpmrepository:01903baf-dbe0-710a-bfb5-e0392927e04e",
        "shared:prn:rpm.rpmrepository:01903baf-d818-765e-8cba-72e027fddda1",
        "shared:prn:core.domain:01902cd3-9252-72fe-9069-58fc3086c0cf"
      ]
    }
    ```
