#!/usr/bin/env bash

# Variables
if [ $# -eq 0 ]; then
  BASE_PATH="foo"
else
  BASE_PATH="$1"
fi
export BASE_PATH

# Create RPM distribution for publication
pulp rpm distribution create \
  --name "${DIST_NAME}" \
  --base-path "${BASE_PATH}" \
  --publication "${PUBLICATION_HREF}"

# After the task is complete, it gives us a new distribution
pulp rpm distribution show --name "${DIST_NAME}"
