#!/usr/bin/env bash

# Copy contnet from one repository version to another
echo "Copy Repository Version to another."
export TASK_URL=$(http POST $BASE_ADDR$REPO_HREF'modify'/ \
    base_version=$REPOVERSION_HREF_WITH_PKG | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_URL

# After the task is complete, it gives us a new repository version
echo "Set REPOVERSION_HREF from finished task."
export REPOVERSION_HREF=$(http $BASE_ADDR$TASK_URL| jq -r '.created_resources | first')

echo "Inspecting RepositoryVersion."
http $BASE_ADDR$REPOVERSION_HREF