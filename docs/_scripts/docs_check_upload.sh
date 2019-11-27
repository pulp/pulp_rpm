#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# NOTE: These scripts use httpie, jq, curl and requires a .netrc for authentication with Pulp

# From the _scripts directory, run with `source docs_check_upload_publish.sh` (source to preserve
# the environment variables)

source base.sh
source repo.sh

source artifact.sh
source package.sh
source add_remove.sh
source advisory.sh
source copy.sh

source publication.sh
source distribution.sh
source download.sh