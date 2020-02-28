#!/usr/bin/env bash

BASE_URL=$(http ${BASE_ADDR}${DISTRIBUTION_HREF} | jq -r '.base_url')
PUBLIC_KEY_URL=${BASE_URL}/repodata/public.key

echo "Setting up a YUM repository."
sudo dnf config-manager --add-repo ${BASE_URL}
sudo dnf config-manager --save --setopt=${REPO_NAME}.gpgcheck=0 \
    --setopt=${REPO_NAME}.repo_gpgcheck=1 --setopt=${REPO_NAME}.gpgkey=${PUBLIC_KEY_URL}

sudo dnf install -y walrus
