#!/bin/sh

set -euv

if [[ "$TEST" == "upgrade" ]]; then
    exit
fi

cmd_stdin_prefix bash -c "cat > /var/lib/pulp/scripts/sign-metadata.sh" < "$GITHUB_WORKSPACE"/pulp_rpm/tests/functional/sign-metadata.sh

curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-KEY-pulp-qe | cmd_stdin_prefix su pulp -c "cat > /tmp/GPG-KEY-pulp-qe"
curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-pulp-qe | cmd_stdin_prefix su pulp -c "gpg --import"
echo "6EDF301256480B9B801EBA3D05A5E6DA269D9D98:6:" | cmd_stdin_prefix gpg --import-ownertrust
cmd_prefix chmod a+x /var/lib/pulp/scripts/sign-metadata.sh

cmd_prefix su pulp -c "pulpcore-manager add-signing-service sign-metadata /var/lib/pulp/scripts/sign-metadata.sh \"Pulp QE\""

echo "machine pulp
login admin
password password
" > ~/.netrc
