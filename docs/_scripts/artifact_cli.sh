#!/usr/bin/env bash

# Get an RPM package
if [[ -n "$1" ]]; then
  export REMOTE_FILE="$1"
else
  export REMOTE_FILE="https://fixtures.pulpproject.org/rpm-signed/squirrel-0.1-1.noarch.rpm"
fi
curl -O "${REMOTE_FILE}"
PKG="$(basename ${REMOTE_FILE})"
export PKG

# Upload it as an Artifact
echo "Upload an RPM package."
ARTIFACT_HREF=$(pulp artifact upload --file "${PKG}" | jq -r '.pulp_href')
ARTIFACT_SHA256=$(pulp show --href "${ARTIFACT_HREF}" | jq -r '.sha256')
export ARTIFACT_HREF
export ARTIFACT_SHA256

echo "Inspecting artifact."
pulp show --href "${ARTIFACT_HREF}"
