#!/usr/bin/env sh

export BASE_ADDR=http://pulp:80
export CONTENT_ADDR=http://pulp:80

cd docs/_scripts/
bash docs_check_upload.sh
bash docs_check_sync.sh
bash docs_check_copy.sh
