#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie, jq, curl and requires a .netrc for authentication with Pulp

# From the _scripts directory, run with `source docs_check_copy.sh` (source to preserve
# the environment variables)

export REPO_NAME="delete-repo"
export DIST_NAME="delete-dist"
export REMOTE_ARTIFACT="https://fixtures.pulpproject.org/rpm-signed/penguin-0.9.1-1.noarch.rpm"

source base.sh
source repo.sh "$REPO_NAME"

source artifact.sh $REMOTE_ARTIFACT
source package.sh
source remove_content.sh
