#!/usr/bin/env bash

# Create new RPM remote
if [ $# -eq 0 ]; then
  REMOTE_NAME="bar"
else
  REMOTE_NAME="$1"
fi
export REMOTE_NAME

echo "Creating a remote that points to an external source of files."
pulp rpm remote create \
    --name "${REMOTE_NAME}" \
    --url 'https://fixtures.pulpproject.org/rpm-unsigned/' \
    --policy 'on_demand'

echo "Export an environment variable for the new remote URI."
REMOTE_HREF=$(pulp rpm remote show --name "${REMOTE_NAME}" | jq -r '.pulp_href')
export REMOTE_HREF

echo "Inspecting new Remote."
pulp rpm remote show --name "${REMOTE_NAME}"
