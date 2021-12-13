#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.
# NOTE: These scripts use httpie (requires a .netrc for authentication), jq, curl and pulp-cli
# From the _scripts directory, run with `source docs_check_install_with_signed_repodata.sh` (source
# to preserve the environment variables)
export REPO_NAME="signed-repo"
export REMOTE_NAME="signed-remote"
export DIST_NAME="signed-dist"

source base_cli.sh

source repo_with_signing_service_cli.sh "${REPO_NAME}"
source remote_cli.sh "${REMOTE_NAME}"
source sync_cli.sh
source publication_cli.sh
source distribution_cli.sh "${DIST_NAME}"
source install_from_signed_repository_cli.sh
