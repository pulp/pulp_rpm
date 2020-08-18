#!/usr/bin/env bash

# Get an RPM package
if [[ -n "$1" ]]; then
  export REMOTE_FILE="$1"
else
  export REMOTE_FILE="https://fixtures.pulpproject.org/rpm-signed/squirrel-0.1-1.noarch.rpm"
fi
curl -O "$REMOTE_FILE"
PKG="$(basename $REMOTE_FILE)"
export PKG

# Upload it as an Artifact
echo "Upload an RPM package."
ARTIFACT_HREF=$(http --form POST "$BASE_ADDR"/pulp/api/v3/artifacts/ \
    file@./"$PKG" | jq -r '.pulp_href')
export ARTIFACT_HREF

echo "Inspecting artifact."
http "$BASE_ADDR""$ARTIFACT_HREF"
