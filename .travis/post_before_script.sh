#!/bin/sh

set -euv

# Aliases for running commands in the pulp-worker container.
PULP_WORKER_PODS="$(sudo kubectl get pods | grep -E -o "pulp-worker-(\w+)-(\w+)")"

for POD in ${PULP_WORKER_PODS}
do
CMD_WORKER_PREFIX="sudo kubectl exec -i $POD -- "
${CMD_WORKER_PREFIX} bash -c "cat > /root/sign-metadata.sh" < "$TRAVIS_BUILD_DIR"/pulp_rpm/tests/functional/sign-metadata.sh

curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-pulp-qe | ${CMD_WORKER_PREFIX} gpg --import
${CMD_WORKER_PREFIX} chmod a+x /root/sign-metadata.sh

KEY_FINGERPRINT="6EDF301256480B9B801EBA3D05A5E6DA269D9D98"
TRUST_LEVEL="6"
echo "$KEY_FINGERPRINT:$TRUST_LEVEL:" | ${CMD_WORKER_PREFIX} gpg --import-ownertrust
done

CREATE_SIGNING_SERVICE="from pulpcore.app.models.content import AsciiArmoredDetachedSigningService; AsciiArmoredDetachedSigningService.objects.create(name='sign-metadata', script='/root/sign-metadata.sh')"
${CMD_WORKER_PREFIX} bash -c "django-admin shell -c \"${CREATE_SIGNING_SERVICE}\""
