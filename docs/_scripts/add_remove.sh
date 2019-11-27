#!/usr/bin/env bash

# Add created RPM content to repository
echo "Add created RPM Package to repository."
export TASK_URL=$(http POST $BASE_ADDR$REPO_HREF'modify/' \
    add_content_units:="[\"$PACKAGE_HREF\"]" | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_URL

# After the task is complete, it gives us a new repository version
echo "Set REPOVERSION_HREF from finished task."
export REPOVERSION_HREF_WITH_PKG=$(http $BASE_ADDR$TASK_URL| jq -r '.created_resources | first')

echo "Inspecting RepositoryVersion."
http $BASE_ADDR$REPOVERSION_HREF_WITH_PKG