# Prune Repository Content

A workflow that can be useful for specific kinds of installation is the "prune" workflow.
For repositories that see frequent updates followed by long periods of stability, it can
be desirable to eventually "age out" RPMs that have been superseded, after a period of time.

The `/pulp/api/v3/rpm/prune/` API exists to provide to the repository-owner/admin a tool to
accomplish this workflow.

- `repo_hrefs` allows the user to specify a list of specific `RpmRepository` HREFs, or 
the wildcard "*" to prune all repositories available in the user's domain.
- `keep_days` allows the user to specify the number of days to allow "old" content to remain in the
repository. The default is 14 days.
- `dry_run` is available as a debugging tool. Instead of actually-pruning, it will log to Pulp's system
log the Packages it **would have pruned**, while making no actual changes.

This workflow will operate on the `latest_version` of the specified RpmRepositor(ies), creating a new RepositoryVersion
with the pruned list of Packages. All the "standard rules" apply at that point:

- Space is not reclaimed unless the older versions are deleted/removed (e.g., older versions are removed manually or `retain_repository_versions` is 1) and orphan-cleanup runs.
- The version must be published to generate the repo-metadata reflecting the new content (e.g., a new Publication is created or`autopublish` is `True`).
- The version will not be available until it is Distributed (e.g. a Distribution is created to point to the new Publication or a Distribution exists that points at the **Repository** directly)

!!! note

    Support for `/prune/` is not yet available in `pulp-cli`. Until it is, this relies on the direct REST calls
    to invoke the API.

!!! note

    This workflow dispatches a separate task for each repository being pruned. In order to avoid using all available
    workers (and hence blocking regular Pulp processing), the prune workflow will consume no more workers than are
    specified by the `PRUNE_WORKERS_MAX` setting, defaulting to 5.

## Example

=== "Prune a repository"

    ```bash 
    $ http POST :5001/pulp/api/v3/rpm/prune/ \
      repo_hrefs:='["/pulp/api/v3/repositories/rpm/rpm/018f73d1-8ba2-779c-8956-854b33b6899c/"]' \
      keep_days=0 \
      dry_run=True
    ``` 

=== "Output"

    ```json
    {
        "task_group": "/pulp/api/v3/task-groups/018f7468-a024-7330-b65e-991203d49064/"
    }
    $ pulp show --href /pulp/api/v3/task-groups/018f7468-a024-7330-b65e-991203d49064/
    {
      "pulp_href": "/pulp/api/v3/task-groups/018f7468-a024-7330-b65e-991203d49064/",
      "description": "Prune old Packages.",
      "all_tasks_dispatched": true,
      "waiting": 0,
      "skipped": 0,
      "running": 0,
      "completed": 2,
      "canceled": 0,
      "failed": 0,
      "canceling": 0,
      "group_progress_reports": [
        {
          "message": "Pruning old Packages",
          "code": "rpm.package.prune",
          "total": 1,
          "done": 1,
          "suffix": null
        }
      ],
      "tasks": [
        {
          "pulp_href": "/pulp/api/v3/tasks/018f7468-a058-7e11-a57d-db9096eb16bc/",
          "pulp_created": "2024-05-14T00:02:44.953250Z",
          "pulp_last_updated": "2024-05-14T00:02:44.953262Z",
          "name": "pulp_rpm.app.tasks.prune.prune_packages",
          "state": "completed",
          "unblocked_at": "2024-05-14T00:02:44.974458Z",
          "started_at": "2024-05-14T00:02:45.042580Z",
          "finished_at": "2024-05-14T00:02:45.262785Z",
          "worker": "/pulp/api/v3/workers/018f743a-d793-78df-b3e9-7cca5e20b99b/"
        },
        {
          "pulp_href": "/pulp/api/v3/tasks/018f7468-a16f-7da0-a530-67bcbd003d6a/",
          "pulp_created": "2024-05-14T00:02:45.231599Z",
          "pulp_last_updated": "2024-05-14T00:02:45.231611Z",
          "name": "pulp_rpm.app.tasks.prune.prune_repo_packages",
          "state": "completed",
          "unblocked_at": "2024-05-14T00:02:45.258585Z",
          "started_at": "2024-05-14T00:02:45.321801Z",
          "finished_at": "2024-05-14T00:02:45.504732Z",
          "worker": "/pulp/api/v3/workers/018f743a-d85b-77d8-80e7-53850c2b878c/"
        }
      ]
    }
    ```

=== "Show Spawned Task"

    ```bash
    $ pulp task show --href /pulp/api/v3/tasks/018f7468-a16f-7da0-a530-67bcbd003d6a/
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/018f7468-a16f-7da0-a530-67bcbd003d6a/",
      "pulp_created": "2024-05-14T00:02:45.231599Z",
      "pulp_last_updated": "2024-05-14T00:02:45.231611Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.prune.prune_repo_packages",
      "logging_cid": "9553043efcb74085a32606569f230610",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-05-14T00:02:45.258585Z",
      "started_at": "2024-05-14T00:02:45.321801Z",
      "finished_at": "2024-05-14T00:02:45.504732Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/018f743a-d85b-77d8-80e7-53850c2b878c/",
      "parent_task": "/pulp/api/v3/tasks/018f7468-a058-7e11-a57d-db9096eb16bc/",
      "child_tasks": [],
      "task_group": "/pulp/api/v3/task-groups/018f7468-a024-7330-b65e-991203d49064/",
      "progress_reports": [
        {
          "message": "Pruning unfoo",
          "code": "rpm.package.prune.repository",
          "state": "completed",
          "total": 4,
          "done": 0,
          "suffix": null
        }
      ],
      "created_resources": [],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:018f73d1-8ba2-779c-8956-854b33b6899c",
        "/pulp/api/v3/repositories/rpm/rpm/018f73d1-8ba2-779c-8956-854b33b6899c/",
        "rpm-prune-worker-0",
        "shared:prn:core.domain:018e770d-1009-786d-a08a-36acd238d229",
        "shared:/pulp/api/v3/domains/018e770d-1009-786d-a08a-36acd238d229/"
      ]
    }
    ```