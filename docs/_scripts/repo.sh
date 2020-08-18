#!/usr/bin/env bash

# Create RPM repository
if [ $# -eq 0 ]; then
  REPO_NAME="foo"
else
  REPO_NAME="$1"
fi
export REPO_NAME

echo "Creating a new repository named $REPO_NAME."
REPO_HREF=$(http POST "$BASE_ADDR"/pulp/api/v3/repositories/rpm/rpm/ name="$REPO_NAME" \
    | jq -r '.pulp_href')
export REPO_HREF

echo "Inspecting Repository."
http "$BASE_ADDR""$REPO_HREF"