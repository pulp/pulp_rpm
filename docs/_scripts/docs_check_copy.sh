#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie, jq, curl and requires a .netrc for authentication with Pulp

# From the _scripts directory, run with `source docs_check_copy.sh` (source to preserve
# the environment variables)

export REPO_NAME="copy-repo"
export DIST_NAME="copy-dist"
export REMOTE_ARTIFACT="https://fixtures.pulpproject.org/rpm-signed/shark-0.1-1.noarch.rpm"

source base.sh
source repo.sh "$REPO_NAME"

source artifact.sh $REMOTE_ARTIFACT
source package.sh
source copy_basic.sh

source publication.sh
source distribution.sh "$DIST_NAME"
source download.sh
