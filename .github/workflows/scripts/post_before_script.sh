#!/bin/sh

set -euv

cmd_stdin_prefix bash -c "cat > /root/sign-metadata.sh" < "$GITHUB_WORKSPACE"/pulp_rpm/tests/functional/sign-metadata.sh

cmd_prefix bash -c "curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-pulp-qe | gpg --import"
cmd_prefix chmod a+x /root/sign-metadata.sh

KEY_FINGERPRINT="6EDF301256480B9B801EBA3D05A5E6DA269D9D98"
TRUST_LEVEL="6"
echo "$KEY_FINGERPRINT:$TRUST_LEVEL:" | cmd_stdin_prefix gpg --import-ownertrust

CREATE_SIGNING_SERVICE="from pulpcore.app.models.content import AsciiArmoredDetachedSigningService; AsciiArmoredDetachedSigningService.objects.create(name='sign-metadata', script='/root/sign-metadata.sh')"
cmd_prefix bash -c "django-admin shell -c \"${CREATE_SIGNING_SERVICE}\""


echo "machine pulp
login admin
password password
" > ~/.netrc
