#!/usr/bin/env bash

# Create RPM repository
if [ $# -eq 0 ]; then
  REPO_NAME="foo"
else
  REPO_NAME="$1"
fi
export REPO_NAME

echo "Fetching the signing service."
SIGNING_SERVICE_HREF=$(http "$BASE_ADDR"/pulp/api/v3/signing-services/?name="sign-metadata" \
    | jq -r '.results[0].pulp_href')
export SIGNING_SERVICE_HREF

echo "Creating a new repository named $REPO_NAME."
REPO_HREF=$(http POST "$BASE_ADDR"/pulp/api/v3/repositories/rpm/rpm/ name="$REPO_NAME" \
    metadata_signing_service="$SIGNING_SERVICE_HREF" \
    | jq -r '.pulp_href')
export REPO_HREF

echo "Inspecting Repository."
http "$BASE_ADDR""$REPO_HREF"
