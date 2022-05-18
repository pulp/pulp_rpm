#!/usr/bin/env bash

# Create RPM package from an artifact
echo "Create RPM content from artifact."
PACKAGE_HREF=$(pulp rpm content create \
               --sha256 "${ARTIFACT_SHA256}" \
               | jq -r '.pulp_href')
export PACKAGE_HREF

echo "Inspecting Package."
pulp show --href "${PACKAGE_HREF}"
