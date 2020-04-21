#!/usr/bin/env bash

# Create RPM repository
if [ $# -eq 0 ]; then
  export REPO_NAME="foo"
else
  export REPO_NAME="$1"
fi

echo "Creating a new repository named $REPO_NAME."
export REPO_HREF=$(http POST $BASE_ADDR/pulp/api/v3/repositories/rpm/rpm/ name=$REPO_NAME \
    | jq -r '.pulp_href')

echo "Inspecting Repository."
http $BASE_ADDR$REPO_HREF