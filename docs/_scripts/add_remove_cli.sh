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
