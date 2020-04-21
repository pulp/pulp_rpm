#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie, jq, curl and requires a .netrc for authentication with Pulp

# From the _scripts directory, run with `source docs_check_upload_publish.sh` (source to preserve
# the environment variables)

export REPO_NAME="upload-repo"
export DIST_NAME="upload-dist"

source base.sh
source repo.sh "$REPO_NAME"

source artifact.sh
source package.sh
source add_remove.sh
source advisory.sh
source copy.sh

source publication.sh
source distribution.sh "$DIST_NAME"
source download.sh