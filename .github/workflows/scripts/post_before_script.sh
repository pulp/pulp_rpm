#!/bin/sh

set -euv

if [[ "$TEST" == "upgrade" ]]; then
    exit
fi

cmd_stdin_prefix bash -c "cat > /root/sign-metadata.sh" < "$GITHUB_WORKSPACE"/pulp_rpm/tests/functional/sign-metadata.sh

cmd_prefix bash -c "curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-pulp-qe | gpg --import"
cmd_prefix bash -c "curl -O -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-KEY-pulp-qe"
cmd_prefix chmod a+x /root/sign-metadata.sh

KEY_FINGERPRINT="6EDF301256480B9B801EBA3D05A5E6DA269D9D98"
TRUST_LEVEL="6"
echo "$KEY_FINGERPRINT:$TRUST_LEVEL:" | cmd_stdin_prefix gpg --import-ownertrust

cmd_prefix bash -c "pulpcore-manager add-signing-service sign-metadata /root/sign-metadata.sh \"Pulp QE\""

echo "machine pulp
login admin
password password
" > ~/.netrc
