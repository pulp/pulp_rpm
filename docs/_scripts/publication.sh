#!/usr/bin/env bash

# Create RPM publication
echo "Create a task to create a publication."
TASK_URL=$(http POST "$BASE_ADDR"/pulp/api/v3/publications/rpm/rpm/ \
    repository="$REPO_HREF" metadata_checksum_type=sha256 | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished "$BASE_ADDR""$TASK_URL"

# After the task is complete, it gives us a new publication
echo "Set PUBLICATION_HREF from finished task."
PUBLICATION_HREF=$(http "$BASE_ADDR""$TASK_URL"| jq -r '.created_resources | first')
export PUBLICATION_HREF

echo "Inspecting Publication."
http "$BASE_ADDR""$PUBLICATION_HREF"
