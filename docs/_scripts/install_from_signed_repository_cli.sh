#!/usr/bin/env bash

BASE_URL=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_url')
BASE_PATH=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_path')
PUBLIC_KEY_URL="${BASE_URL}"/repodata/repomd.xml.key

echo "Setting up a YUM repository."
sudo dnf config-manager --add-repo "${BASE_URL}"
sudo dnf config-manager --save \
    --setopt=*"${BASE_PATH}".gpgcheck=0 \
    --setopt=*"${BASE_PATH}".repo_gpgcheck=1 \
    --setopt=*"${BASE_PATH}".gpgkey="${PUBLIC_KEY_URL}"

sudo dnf install --downloadonly -y walrus
