#!/usr/bin/env bash

# Remove content from repository
echo "Removing content from ${REPO_NAME}"
pulp rpm repository version destroy --repository $REPO_NAME

echo "Removing orphan rpm contents"
pulp orphan cleanup --content-hrefs $(pulp rpm content list | jq -cr '.|map(.pulp_href)') --protection-time 0

echo "Checking rpm contents"
pulp rpm repository content list --repository $REPO_NAME
