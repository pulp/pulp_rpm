#!/usr/bin/env bash

# Add content unit to the repository
echo "Add and then remove content from repository."

TASK_HREF=$(pulp rpm repository content modify \
            --repository "${REPO_NAME}" \
            --add-content "[{\"pulp_href\": \"${PACKAGE_HREF}\"}]" \
            2>&1 >/dev/null | awk '{print $4}')
REPOVERSION_HREF=$(pulp show --href "${TASK_HREF}" | jq -r '.created_resources | first')
REPOVERSION=$(echo "${REPOVERSION_HREF}" | cut -d "/" -f 10)
export REPOVERSION

# Remove content units from the repository
pulp rpm repository content modify \
  --repository "${REPO_NAME}" \
  --remove-content "[{\"pulp_href\": \"${PACKAGE_HREF}\"}]"

# Clone a repository (can be composed with addition or removal of units)
# This operation will create a new repository version in the current repository which
# is a copy of the one specified as the 'base_version', regardless of what content
# was previously present in the repository.
echo "Clone a repository with a content."
TASK_HREF=$(pulp rpm repository content modify \
            --repository "${REPO_NAME}" \
            --base-version "${REPOVERSION}" \
            2>&1 >/dev/null | awk '{print $4}')

# After the task is complete, it gives us a new repository version
echo "Set REPOVERSION_HREF from finished task."
REPOVERSION_HREF=$(pulp show --href "${TASK_HREF}" | jq -r '.created_resources | first')
export REPOVERSION_HREF

echo "Inspecting RepositoryVersion."
pulp show --href "${REPOVERSION_HREF}"
