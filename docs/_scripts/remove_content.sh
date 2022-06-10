#!/usr/bin/env bash

# Remove content from repository
echo "Removing content from ${REPO_NAME}"
export LATEST_VERSION=$(http "$BASE_ADDR/pulp/api/v3/repositories/rpm/rpm/?name=${REPO_NAME}"  | jq -r '.results[0].latest_version_href')
http DELETE "${BASE_ADDR}${LATEST_VERSION}"

echo "Removing orphan rpm contents"
http POST "$BASE_ADDR"/pulp/api/v3/orphans/cleanup/ orphan_protection_time=0

echo "Checking rpm contents"
export LATEST_VERSION_HREF=$(http "${BASE_ADDR}/pulp/api/v3/repositories/rpm/rpm/?name=${REPO_NAME}" | jq -r .results[0].latest_version_href)
http "${BASE_ADDR}/pulp/api/v3/content/rpm/packages/?repository_version=${LATEST_VERSION_HREF}"
