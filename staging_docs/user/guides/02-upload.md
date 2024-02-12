# Upload Content

Content can be added to a repository not only by synchronizing from a remote source but also by
uploading.

### Add content to repository `foo`

If there is content already in Pulp, you can add it to a repository using `content modify`:

=== "Add Package to a Repository"

    ```bash
    #!/usr/bin/env bash
    
    # Add created RPM content to repository
    echo "Add created RPM Package to repository."
    TASK_HREF=$(pulp rpm repository content modify \
                --repository "${REPO_NAME}" \
                --add-content "[{\"pulp_href\": \"${PACKAGE_HREF}\"}]" \
                2>&1 >/dev/null | awk '{print $4}')
    
    # After the task is complete, it gives us a new repository version
    echo "Set REPOVERSION_HREF from finished task."
    REPOVERSION_HREF=$(pulp show --href "${TASK_HREF}" \
                       | jq -r '.created_resources | first')
    
    echo "Inspecting RepositoryVersion."
    pulp show --href "${REPOVERSION_HREF}"
    ```

=== "Output"

    ```json
    {
        "base_version": null,
        "content_summary": {
            "added": {
                "rpm.package": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version_added=/pulp/api/v3/repositories/rpm/rpm/805de89c-1b1d-432c-993e-3eb9a3fedd22/versions/1/"
                }
            },
            "present": {
                "rpm.package": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/rpm/packages/?repository_version=/pulp/api/v3/repositories/rpm/rpm/805de89c-1b1d-432c-993e-3eb9a3fedd22/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1,
        "pulp_created": "2019-11-27T13:48:18.326333Z",
        "pulp_href": "/pulp/api/v3/repositories/rpm/rpm/805de89c-1b1d-432c-993e-3eb9a3fedd22/versions/1/"
    }
    ```

!!! note
    It is recommended to omit the `relative_path` and have Pulp generate a common pool location.
    This will be `/repo/Packages/s/squirrel-0.1-1.noarch.rpm` as shown below.

    When specifying a `relative_path`, make sure to add the exact name of the package
    including its name, version, release and arch as in `squirrel-0.1-1.noarch.rpm`.
    It is composed of the `name-version-release.arch.rpm`.

    Example:

    ```none
    relative_path="squirrel-0.1-1.noarch.rpm"
    ```

### Advisory upload

Advisory upload requires a file or an artifact containing advisory information in the JSON format.
Repository is an optional argument to create new repository version with uploaded advisory.

=== "Upload an Advisory"

    ```
    #!/usr/bin/env bash
    
    # Get advisory
    echo '{
        "updated": "2014-09-28 00:00:00",
        "issued": "2014-09-24 00:00:00",
        "id": "RHSA-XXXX:XXXX"
    }' > advisory.json
    export ADVISORY="advisory.json"
    
    # Upload advisory
    echo "Upload advisory in JSON format."
    TASK_URL=$(http --form POST "${BASE_ADDR}"/pulp/api/v3/content/rpm/advisories/ \
        file@./"${ADVISORY}" repository="${REPO_HREF}" | jq -r '.task')
    export TASK_URL
    
    # Poll the task (here we use a function defined in docs/_scripts/base.sh)
    wait_until_task_finished "${BASE_ADDR}""${TASK_URL}"
    
    # After the task is complete, it gives us a new repository version
    echo "Set ADVISORY_HREF from finished task."
    ADVISORY_HREF=$(http "${BASE_ADDR}""${TASK_URL}" \
                    | jq -r '.created_resources | .[] | match(".*advisories.*") | .string')
    export ADVISORY_HREF
    
    echo "Inspecting advisory."
    pulp show --href "${ADVISORY_HREF}"
    ```

=== "Output"

    ```json
    {
        "artifact": "/pulp/api/v3/artifacts/b4e3a95c-eb82-410e-8f90-aba59d573058/",
        "description": "",
        "fromstr": "nobody@redhat.com",
        "id": "RHSA-XXXX:XXXX",
        "issued_date": "2014-09-24 00:00:00",
        "pkglist": [],
        "pulp_created": "2019-11-27T13:48:20.364919Z",
        "pulp_href": "/pulp/api/v3/content/rpm/advisories/51169df4-f7c6-46df-953c-1714e5dd5869/",
        "pushcount": "",
        "reboot_suggested": false,
        "references": [],
        "release": "",
        "rights": "",
        "severity": "",
        "solution": "",
        "status": "",
        "summary": "",
        "title": "",
        "type": "",
        "updated_date": "",
        "version": ""
    }
    ```
