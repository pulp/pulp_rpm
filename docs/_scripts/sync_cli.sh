#!/usr/bin/env bash

# Sync repository foo using remote bar
echo "Create a task to sync the repository using the remote."
pulp rpm repository update --name "${REPO_NAME}" --remote "${REMOTE_NAME}"
TASK_HREF=$(pulp rpm repository sync --name "${REPO_NAME}" \
            2>&1 >/dev/null | awk '{print $4}')

echo "Set REPOVERSION_HREF from finished task."
REPOVERSION_HREF=$(pulp show --href "${TASK_HREF}"| jq -r '.created_resources | first')
export REPOVERSION_HREF

echo "Inspecting RepositoryVersion."
pulp show --href "${REPOVERSION_HREF}"
