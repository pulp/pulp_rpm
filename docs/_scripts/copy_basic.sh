#!/usr/bin/env bash

# Add content unit to the repository
echo "Add and then remove content from repository."
TASK_URL=$(http POST "$BASE_ADDR""$REPO_HREF"'modify'/ add_content_units:="[\"$PACKAGE_HREF\"]" | jq -r '.task')
wait_until_task_finished "$BASE_ADDR""$TASK_URL"
REPOVERSION_HREF_WITH_PKG=$(http "$BASE_ADDR""$TASK_URL" | jq -r '.created_resources | first')
export REPOVERSION_HREF_WITH_PKG

# Remove content units from the repository
http POST "$BASE_ADDR""$REPO_HREF"'modify'/ remove_content_units:="[\"$PACKAGE_HREF\"]"

# Clone a repository (can be composed with addition or removal of units)
# This operation will create a new repository version in the current repository which
# is a copy of the one specified as the 'base_version', regardless of what content
# was previously present in the repository.
echo "Clone a repository with a content."
TASK_URL=$(http POST "$BASE_ADDR""$REPO_HREF"'modify'/ \
    base_version="$REPOVERSION_HREF_WITH_PKG" | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished "$BASE_ADDR""$TASK_URL"

# After the task is complete, it gives us a new repository version
echo "Set REPOVERSION_HREF from finished task."
REPOVERSION_HREF=$(http "$BASE_ADDR""$TASK_URL"| jq -r '.created_resources | first')
export REPOVERSION_HREF

echo "Inspecting RepositoryVersion."
http "$BASE_ADDR""$REPOVERSION_HREF"
