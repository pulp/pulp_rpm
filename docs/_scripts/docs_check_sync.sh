#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie, jq and requires a .netrc for authentication with Pulp

# From the _scripts directory, run with `source docs_check_sync_publish.sh` (source to preserve the
# environment variables)

export REPO_NAME="sync-repo"
export DIST_NAME="sync-dist"

source base.sh

source repo.sh "$REPO_NAME"
source remote.sh
source sync.sh

source publication.sh
source distribution.sh "$DIST_NAME"

source download.sh