#!/usr/bin/env bash

# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# From the _scripts directory, run with `source docs_check_install_with_signed_repodata.sh` (source
# to preserve the environment variables)
source base.sh

source repo_with_signing_service.sh
source remote.sh
source sync.sh
source publication.sh
source distribution.sh
source install_from_signed_repository.sh
