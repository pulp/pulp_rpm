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

    This workflow dispatches a separate task for each repository being pruned. In order to avoid using all available
    workers (and hence blocking regular Pulp processing), the prune workflow will consume no more workers than are
    specified by the `PRUNE_WORKERS_MAX` setting, defaulting to 5.

## Example

=== "Setup"

    ```bash
    pulp rpm remote create --name zoo --policy on_demand --url https://fixtures.pulpproject.org/rpm-signed/
    pulp rpm repository create --name zoo --remote zoo
    pulp rpm repository sync --name zoo
    ```

=== "Prune a repository"

    ```bash 
    $ pulp rpm prune-packages --repository zoo --keep-days 0 --dry-run
    Started background task group /pulp/api/v3/task-groups/019036ae-04c5-79b4-bc0b-e31be3372c8a/
    $ pulp task-group show --href /pulp/api/v3/task-groups/019036ae-04c5-79b4-bc0b-e31be3372c8a/
    ``` 

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/task-groups/019036ae-04c5-79b4-bc0b-e31be3372c8a/",
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
          "pulp_href": "/pulp/api/v3/tasks/019036ae-04d0-79e8-97eb-f4ac6778d1a1/",
          "pulp_created": "2024-06-20T17:24:52.561964Z",
          "pulp_last_updated": "2024-06-20T17:24:52.561999Z",
          "name": "pulp_rpm.app.tasks.prune.prune_packages",
          "state": "completed",
          "unblocked_at": "2024-06-20T17:24:52.579086Z",
          "started_at": "2024-06-20T17:24:52.619739Z",
          "finished_at": "2024-06-20T17:24:52.684361Z",
          "worker": "/pulp/api/v3/workers/01902cd4-536f-7e31-aec9-059c55ba427c/"
        },
        {
          "pulp_href": "/pulp/api/v3/tasks/019036ae-052c-7b42-9716-61c7c289662c/",
          "pulp_created": "2024-06-20T17:24:52.652887Z",
          "pulp_last_updated": "2024-06-20T17:24:52.652897Z",
          "name": "pulp_rpm.app.tasks.prune.prune_repo_packages",
          "state": "completed",
          "unblocked_at": "2024-06-20T17:24:52.669390Z",
          "started_at": "2024-06-20T17:24:52.721946Z",
          "finished_at": "2024-06-20T17:24:52.774561Z",
          "worker": "/pulp/api/v3/workers/01902cd4-51ff-78d3-9aa7-3d2dde187e18/"
        }
      ]
    }
    ```

=== "Show spawned task pruning repository 'zoo'"

    ```bash
    $ pulp task show --href /pulp/api/v3/tasks/019036ae-052c-7b42-9716-61c7c289662c/
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/tasks/019036ae-052c-7b42-9716-61c7c289662c/",
      "pulp_created": "2024-06-20T17:24:52.652887Z",
      "pulp_last_updated": "2024-06-20T17:24:52.652897Z",
      "state": "completed",
      "name": "pulp_rpm.app.tasks.prune.prune_repo_packages",
      "logging_cid": "4008405185ef4b40b24581eefece35ab",
      "created_by": "/pulp/api/v3/users/1/",
      "unblocked_at": "2024-06-20T17:24:52.669390Z",
      "started_at": "2024-06-20T17:24:52.721946Z",
      "finished_at": "2024-06-20T17:24:52.774561Z",
      "error": null,
      "worker": "/pulp/api/v3/workers/01902cd4-51ff-78d3-9aa7-3d2dde187e18/",
      "parent_task": "/pulp/api/v3/tasks/019036ae-04d0-79e8-97eb-f4ac6778d1a1/",
      "child_tasks": [],
      "task_group": "/pulp/api/v3/task-groups/019036ae-04c5-79b4-bc0b-e31be3372c8a/",
      "progress_reports": [
        {
          "message": "Pruning zoo",
          "code": "rpm.package.prune.repository",
          "state": "completed",
          "total": 4,
          "done": 0,
          "suffix": null
        }
      ],
      "created_resources": [],
      "reserved_resources_record": [
        "prn:rpm.rpmrepository:019036a6-4f7a-7daa-b2ad-02bd30f4ce01",
        "rpm-prune-worker-0",
        "shared:prn:core.domain:01902cd3-9252-72fe-9069-58fc3086c0cf"
      ]
    }
    ```