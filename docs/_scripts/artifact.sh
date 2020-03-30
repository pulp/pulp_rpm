#!/usr/bin/env bash

# Get an RPM package
curl -O https://repos.fedorapeople.org/pulp/pulp/fixtures/rpm-signed/squirrel-0.1-1.noarch.rpm
export PKG="squirrel-0.1-1.noarch.rpm"

# Upload it as an Artifact
echo "Upload an RPM package."
export ARTIFACT_HREF=$(http --form POST $BASE_ADDR/pulp/api/v3/artifacts/ \
    file@./$PKG | jq -r '.pulp_href')

echo "Inspecting artifact."
http $BASE_ADDR$ARTIFACT_HREF