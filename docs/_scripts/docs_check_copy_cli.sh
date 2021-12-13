#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie (requires a .netrc for authentication), jq, curl and pulp-cli

# From the _scripts directory, run with `source docs_check_copy.sh` (source to preserve
# the environment variables)

export REPO_NAME="copy-repo"
export DIST_NAME="copy-dist"
export REMOTE_ARTIFACT="https://fixtures.pulpproject.org/rpm-signed/shark-0.1-1.noarch.rpm"

source base_cli.sh
source repo_cli.sh "${REPO_NAME}"

source artifact_cli.sh ${REMOTE_ARTIFACT}
source package_cli.sh
source copy_basic_cli.sh

source publication_cli.sh
source distribution_cli.sh "${DIST_NAME}"
source download_cli.sh
