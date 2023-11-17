#!/bin/sh

set -euv

if [[ "$TEST" == "upgrade" ]]; then
    exit
fi

cmd_stdin_prefix bash -c "cat > /var/lib/pulp/scripts/sign-metadata.sh" < "$GITHUB_WORKSPACE"/pulp_rpm/tests/functional/sign-metadata.sh

curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-KEY-fixture-signing | cmd_stdin_prefix su pulp -c "cat > /tmp/GPG-KEY-fixture-signing"
curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-fixture-signing | cmd_stdin_prefix su pulp -c "gpg --import"
echo "0C1A894EBB86AFAE218424CADDEF3019C2D4A8CF:6:" | cmd_stdin_prefix gpg --import-ownertrust
cmd_prefix chmod a+x /var/lib/pulp/scripts/sign-metadata.sh

cmd_prefix su pulp -c "pulpcore-manager add-signing-service sign-metadata /var/lib/pulp/scripts/sign-metadata.sh \"pulp-fixture-signing-key\""

echo "machine pulp
login admin
password password
" > ~/.netrc
