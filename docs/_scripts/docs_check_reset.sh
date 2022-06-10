#!/usr/bin/env bash

# This script (attempts to) clean up the repositories and remotes created by the docs_check_* scripts.
#
# NOTE: This script relies on pulp-cli being installed and configured to point to your Pulp instance.
#
# From the _scripts directory, run with `docs_check_reset.sh`

REPO_NAME="copy-repo"
DIST_NAME="copy-dist"
pulp rpm repository destroy --name "${REPO_NAME}"
pulp rpm distribution destroy --name "${DIST_NAME}"

REPO_NAME="signed-repo"
REMOTE_NAME="signed-remote"
DIST_NAME="signed-dist"
pulp rpm repository destroy --name "${REPO_NAME}"
pulp rpm remote destroy --name "${REMOTE_NAME}"
pulp rpm distribution destroy --name "${DIST_NAME}"

REPO_NAME="sync-repo"
REMOTE_NAME="sync-remote"
DIST_NAME="sync-dist"
pulp rpm repository destroy --name "${REPO_NAME}"
pulp rpm remote destroy --name "${REMOTE_NAME}"
pulp rpm distribution destroy --name "${DIST_NAME}"

REPO_NAME="upload-repo"
DIST_NAME="upload-dist"
pulp rpm repository destroy --name "${REPO_NAME}"
pulp rpm distribution destroy --name "${DIST_NAME}"

REPO_NAME="delete-repo"
pulp rpm repository destroy --name "${REPO_NAME}"

echo "Sleep 60 for orphan-cleanup..."
sleep 60
pulp orphan cleanup --protection-time 1
