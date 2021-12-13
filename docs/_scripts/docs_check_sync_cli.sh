#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie (requires a .netrc for authentication), jq, curl and pulp-cli

# From the _scripts directory, run with `source docs_check_sync_publish.sh` (source to preserve the
# environment variables)

export REPO_NAME="sync-repo"
export REMOTE_NAME="sync-remote"
export DIST_NAME="sync-dist"

source base_cli.sh

source repo_cli.sh "${REPO_NAME}"
source remote_cli.sh "${REMOTE_NAME}"
source sync_cli.sh

source publication_cli.sh
source distribution_cli.sh "${DIST_NAME}"

source download_cli.sh