#!/usr/bin/env bash

# Create new RPM remote
echo "Creating a remote that points to an external source of files."
http POST "$BASE_ADDR"/pulp/api/v3/remotes/rpm/rpm/ \
    name='bar' \
    url='https://fixtures.pulpproject.org/rpm-unsigned/' \
    policy='on_demand'

echo "Export an environment variable for the new remote URI."
REMOTE_HREF=$(http "$BASE_ADDR"/pulp/api/v3/remotes/rpm/rpm/ \
    | jq -r '.results[] | select(.name == "bar") | .pulp_href')
export REMOTE_HREF

echo "Inspecting new Remote."
http "$BASE_ADDR""$REMOTE_HREF"
