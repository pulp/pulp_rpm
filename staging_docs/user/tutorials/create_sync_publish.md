# Create, Sync and Publish a Repository

One of the most common workflows is a fetching content from a remote source and making it
available for users.

## Create an RPM repository `foo`

=== "Create Repo"

    ```bash
    echo "Creating Repository."
    pulp rpm repository create --name foo | jq -r '.pulp_href'
    echo "Inspecting Repository."
    pulp rpm repository show --name foo
    ```

=== "Output"

    ```json
    {
        "description": null,
        "latest_version_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/0/",
        "name": "foo",
        "pulp_created": "2019-11-27T13:30:28.159167Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/",
        "versions_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/"
    }
    ```

RPM Repositories support several additional options.

- metadata_signing_service:
  : See `metadata_signing`.
- retain_package_versions:
  : The maximum number of versions of each package to keep; as new versions of packages are added by upload, sync, or copy, older versions of the same packages are automatically removed. A value of 0 means "unlimited".
- autopublish:
  : If set to True, Pulp will automatically create publications for new repository versions. It is generally intended to be used with the `Distribution` pointing to the repository, i.e. set the `repository` field on the distribution. Newly created publications (from autopublish) will then be made available automatically upon creation.
- retain_repo_versions:
  : Provided by pulpcore, specifies how many repository versions will be kept for a repository. For example, if set to 1, it will keep only the most-recent repository version; the rest will be automatically deleted, together with any associated publications. Note, however, that repository versions that are currently being distributed are "protected", and cannot be removed. This can result in more versions being retained than specified by `retain_repo_versions`.
  
## Create a new remote `bar`

By default `policy='immediate` which means that all the content is downloaded right away.
Specify `policy='on_demand'` to make synchronization of a repository faster and only
to download RPMs whenever they are requested by clients.

=== "Create Remote"

    ```bash
    echo "Creating a remote that points to an external source of files."
    pulp rpm remote create \
        --name bar \
        --url 'https://fixtures.pulpproject.org/rpm-unsigned/' \
        --policy 'on_demand'
    
    echo "Inspecting new Remote."
    pulp rpm remote show --name bar
    ```

=== "Create Remote with Certs"

    Also, you can specify `client_cert` and `client_key` if your remote require authorization with a certificate.
    
    ```bash
    pulp rpm remote create \
        --name='bar' \
        --url "${URL}" \
        --policy on_demand \
        --client-cert @./certificate.crt \
        --client-key @./certificate.key \
        --tls-validation False
    ```

    If you want to use TLS validation you have to provide `ca_cert` too.

=== "Output"

    ```json
    {
        "ca_cert": null,
        "client_cert": null,
        "client_key": null,
        "download_concurrency": 20,
        "name": "bar",
        "policy": "on_demand",
        "proxy_url": null,
        "pulp_created": "2019-11-27T13:30:29.199173Z",
        "pulp_href": "/pulp/api/v3/remotes/rpm/rpm/2ceb5262-a5b2-4297-afdf-a31f7e46dfc5/",
        "pulp_last_updated": "2019-11-27T13:30:29.199187Z",
        "tls_validation": true,
        "url": "https://fixtures.pulpproject.org/rpm-unsigned/"
    }
    ```

!!! note
    While creating a new remote, you may set the field `url` to point to a mirror list feed. Pulp
    fetches the list of available mirrors and tries to download content from the first valid mirror.
    This means that whenever an error occurs during the synchronization, the whole sync process ends
    with an error too.

### Configuration for SLES 12+ repository with authentication

If you would like to sync SLES 12+ repository you will need to specify an authentication as `sles_auth_token`.

You can receive your token with script like this:

```bash
curl -H "Authorization: Token token=YourOrganizationRegistrationCode" \
https://scc.suse.com/connect/subscriptions/products | \
tr "," "\n" | \
grep -i "url" | \
grep -i "SLE-SERVER"
```

Assuming your token is `YourRepositoryToken`, create the remote with the `sles_auth_token` specified.

```bash
pulp rpm remote create \
    --name 'SLESrepo' \
    --url 'https://updates.suse.com/SUSE/Updates/SLE-SERVER/12/x86_64/update/' \
    --policy on_demand \
    --sles-auth-token 'YourRepositoryToken'
```

### Creating a ULN remote

ULN stands for "Unbreakable Linux Network" and refers to the way Oracle in particular, 
[delivers Oracle Linux repositories](https://linux.oracle.com/) to their enterprise customers.
You can use a ULN remote to synchronize repositories from a ULN server to Pulp.
For ULN remotes you must provide your ULN login credentials via the `username`, and `password` parameters, 
and the `url` is the ULN channel, e.g. `uln://ovm2_2.1.1_i386_patch`:

```bash
pulp rpm remote create \
    --name 'ULNRemote' \
    --url 'uln://ovm2_2.1.1_i386_patch' \
    --username 'example@example.com' \
    --password 'changeme'
```

You can also specify the ULN Server base URL for a remote using the `uln_server_base_url` parameter.
If you do not provide this parameter, a sync with the remote will default to the contents of the `DEFAULT_ULN_SERVER_BASE_URL` setting, which is `https://linux-update.oracle.com/` by default.
The [pulpcore settings documentation](site:/pulpcore/docs/admin/learn/settings/) has more on how to change Pulp settings.

Once you have created a ULN remote, you can synchronize it into a RPM repository, just like you would with a RPM remote.

You may also want to consult the [Oracle ULN documentation](https://docs.oracle.com/en/operating-systems/oracle-linux/uln-user/ol_about_uln.html) for more information.

## Sync repository `foo` using remote `bar`

There are 3 sync modes to choose from, using the `--sync-policy` option.

- `additive` (the default) will retain the existing contents of the Pulp repository and add the contents of the remote repository being synced.
- `mirror_content_only` will synchronize the Pulp repository to contain the same content as the one remote repository being synced - removing any existing content that isn't present in the remote repo.
- `mirror_complete` will act as `mirror_content_only` does, but additionally it will automatically create a publication that will be an \_exact\_ bit-for-bit copy of the remote repository being synced, rather than requiring a separate step (or `autopublish`) to generate the metadata later. This will keep repo metadata checksums intact, but is not possible for all repositories, as some use features which are incompatible with creating local clones that are exact copies.

The `--mirror` option is deprecated, `--sync-policy` should be used instead. 
If the `--mirror` option is used, this will change the default `sync_policy` to `mirror_complete`, 
while a value of `--no-mirror` will not change the default `sync_policy`.

Optionally, you can skip `SRPM` packages by using `--skip_type srpm`
option.

Optionally, you can skip kickstart-trees referred to by a parent repository by using `--skip_type treeinfo`

You can combine these options by specifying `--skip_type srpm --skip-type treeinfo`.

By default, sync will only proceed if changes are present in the remote repository (i.e., `--optimize`).
You can override this by specifying `--no-optimize` which will disable optimizations and
run a full sync.

=== "Sync a Repository"

    ```bash
    #!/usr/bin/env bash
    
    # Sync repository foo using remote bar
    echo "Create a task to sync the repository using the remote."
    pulp rpm repository update --name foo --remote bar
    pulp rpm repository sync --name foo 
    # Show resulting latest-version of foo
    pulp pulp rpm repository version --repository foo
    ```

=== "Output"

    ```json
    {
        "base_version": null,
        "content_summary": {
            "added": {
                "rpm.advisory": {
                    "count": 4,
                    "href": "/pulp/api/v3/content/rpm/advisories/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.package": {
                    "count": 35,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagecategory": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagecategories/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagegroup": {
                    "count": 2,
                    "href": "/pulp/api/v3/content/rpm/packagegroups/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagelangpacks": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagelangpacks/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                }
            },
            "present": {
                "rpm.advisory": {
                    "count": 4,
                    "href": "/pulp/api/v3/content/rpm/advisories/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.package": {
                    "count": 35,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagecategory": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagecategories/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagegroup": {
                    "count": 2,
                    "href": "/pulp/api/v3/content/rpm/packagegroups/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                },
                "rpm.packagelangpacks": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packagelangpacks/?repository_version=/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1,
        "pulp_created": "2019-11-27T13:30:31.961788Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/a02ace53-d490-458d-8b93-604fbcd23a9c/versions/1/"
    }
    ```

!!! note
    To set up a regular sync task, use one of the external tools that deal with periodic background jobs.
    Learn more about scheduling tasks [here](site:/pulpcore/workflows/scheduling-tasks.html).

## Create a Publication

A publication can only be created once a sync task completes. You can specify checksum algorithm with the following optional parameters:

- metadata_checksum_type: affects all the repodata, including primary.xml, repomd.xml, etc.
  If not specified, the default SHA256 algorithm will be used.
- package_checksum_type: affects package checksum type in all repo metadata files.
  If not specified, the default SHA256 algorithm will be used.
  Because of on_demand sync, it is possible that the requested checksum is not available.
  In such case the one from the remote repo will be used.
  
=== "Create a Publication"

    ```bash
    #!/usr/bin/env bash
    
    # Create RPM publication
    echo "Create a task to create a publication."
    TASK_HREF=$(pulp rpm publication create \
                --repository "${REPO_NAME}" \
                2>&1 >/dev/null | awk '{print $4}')
    
    # After the task is complete, it gives us a new publication
    echo "Set PUBLICATION_HREF from finished task."
    PUBLICATION_HREF=$(pulp show --href "${TASK_HREF}" | jq -r '.created_resources | first')
    export PUBLICATION_HREF
    
    echo "Inspecting Publication."
    pulp show --href "${PUBLICATION_HREF}"
    ```

=== "Create a Publication with a config.repo"

    You can specify various options for the `config.repo` file by passing them to the `--repo-config` option:
    
    ```bash
    pulp rpm publication create \
       --repository "${REPO_NAME}" \
       --repo-config '{"gpgcheck": 1, "repo-gpgcheck": 1}'
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/publications/rpm/rpm/018d9e89-f231-729a-b9ea-1c489e7b0cef/",
      "pulp_created": "2024-02-12T18:17:37.074463Z",
      "repository_version": "/pulp/api/v3/repositories/rpm/rpm/678798cd-9e08-4c9d-9feb-7dc88412b101/versions/1/",
      "repository": "/pulp/api/v3/repositories/rpm/rpm/678798cd-9e08-4c9d-9feb-7dc88412b101/",
      "checksum_type": "sha256",
      "metadata_checksum_type": "sha256",
      "package_checksum_type": "sha256",
      "gpgcheck": null,
      "repo_gpgcheck": null,
      "sqlite_metadata": false,
      "repo_config": {
        "gpgcheck": 1,
        "repo-gpgcheck": 1
      },
      "compression_type": null
    }
    ```

We encourage users to take a look at the [pulp_rpm API documentation](site:/pulp_rpm/restapi.html#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_create)
to see the default values for these options.

## Create a Distribution for the Publication

=== "Create a Distribution"

    ```bash
    #!/usr/bin/env bash
    
    # Variables
    if [ $# -eq 0 ]; then
      BASE_PATH="foo"
    else
      BASE_PATH="$1"
    fi
    export BASE_PATH
    
    # Create RPM distribution for publication
    pulp rpm distribution create \
      --name "${DIST_NAME}" \
      --base-path "${BASE_PATH}" \
      --publication "${PUBLICATION_HREF}"
    
    # After the task is complete, it gives us a new distribution
    pulp rpm distribution show --name "${DIST_NAME}"
    ```

=== "Output"

    ```json
    {
        "base_path": "foo",
        "base_url": "http://pulp3-source-fedora30.pavels-macbook-pro.example.com/pulp/content/foo",
        "content_guard": null,
        "name": "baz",
        "publication": "/pulp/api/v3/publications/rpm/rpm/c90316fc-bf2a-458a-93b8-d3d75614572f/",
        "pulp_created": "2019-11-27T13:30:38.238857Z",
        "pulp_href": "/pulp/api/v3/distributions/rpm/rpm/c1166d2d-0832-4e90-85fd-e34e94e6a156/"
    }
    ```
