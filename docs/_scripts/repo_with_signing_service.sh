#!/usr/bin/env bash

# Create RPM repository
if [ $# -eq 0 ]; then
  export REPO_NAME="foo"
else
  export REPO_NAME="$1"
fi

echo "Fetching the signing service."
export SIGNING_SERVICE_HREF=$(http ${BASE_ADDR}/pulp/api/v3/signing-services/?name="sign-metadata" \
    | jq -r '.results[0].pulp_href')

echo "Creating a new repository named $REPO_NAME."
export REPO_HREF=$(http POST ${BASE_ADDR}/pulp/api/v3/repositories/rpm/rpm/ name=$REPO_NAME \
    metadata_signing_service=${SIGNING_SERVICE_HREF} \
    | jq -r '.pulp_href')

echo "Inspecting Repository."
http ${BASE_ADDR}${REPO_HREF}
