#!/usr/bin/env bash

# Download a package

# Specify one package from repository used in 'remote.sh'
if [ -z "$PKG" ]; then
  PKG="fox-1.1-2.noarch.rpm"
fi

# The distribution will return a url that can be used by http clients
echo "Setting DISTRIBUTION_BASE_URL, which is used to retrieve content from the content app."
export DISTRIBUTION_BASE_URL=$(http $BASE_ADDR$DISTRIBUTION_HREF | jq -r '.base_url')

# If Pulp was installed without CONTENT_HOST set, it's just the path.
# And httpie will default to localhost:80
if [[ "${DISTRIBUTION_BASE_URL:0:1}" = "/" ]]; then
    DISTRIBUTION_BASE_URL=$CONTENT_ADDR$DISTRIBUTION_BASE_URL
fi

# Download a package from the distribution
http -d $DISTRIBUTION_BASE_URL/Packages/f/$PKG
