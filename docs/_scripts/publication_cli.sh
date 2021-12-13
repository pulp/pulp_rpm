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
