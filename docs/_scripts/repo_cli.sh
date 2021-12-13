#!/usr/bin/env bash

# Create RPM repository
if [ $# -eq 0 ]; then
  REPO_NAME="foo"
else
  REPO_NAME="$1"
fi
export REPO_NAME

echo "Creating a new repository named $REPO_NAME."
REPO_HREF=$(pulp rpm repository create --name "${REPO_NAME}" | jq -r '.pulp_href')
export REPO_HREF

echo "Inspecting Repository."
pulp rpm repository show --name "${REPO_NAME}"