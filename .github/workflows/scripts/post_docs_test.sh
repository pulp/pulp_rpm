#!/usr/bin/env sh

export BASE_ADDR=https://pulp:443
export CONTENT_ADDR=https://pulp:443

cd docs/_scripts/
bash docs_check_upload.sh
bash docs_check_sync.sh
bash docs_check_copy.sh
