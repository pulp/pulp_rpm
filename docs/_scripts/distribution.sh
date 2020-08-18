#!/usr/bin/env bash

# Variables
if [ $# -eq 0 ]; then
  BASE_PATH="foo"
else
  BASE_PATH="$1"
fi
export BASE_PATH

# Create RPM distribution for publication
TASK_URL=$(http POST "$BASE_ADDR"/pulp/api/v3/distributions/rpm/rpm/ \
    publication="$PUBLICATION_HREF" name="$BASE_PATH" base_path="$REPO_NAME" | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished "$BASE_ADDR""$TASK_URL"

# After the task is complete, it gives us a new distribution
echo "Set DISTRIBUTION_HREF from finished task."
DISTRIBUTION_HREF=$(http "$BASE_ADDR""$TASK_URL"| jq -r '.created_resources | first')
export DISTRIBUTION_HREF

echo "Inspecting Distribution."
http "$BASE_ADDR""$DISTRIBUTION_HREF"