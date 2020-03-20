#!/usr/bin/env bash

FILE_PATH=$1
SIGNATURE_PATH="$1.asc"

PUBLIC_KEY_PATH="$(cd "$(dirname $1)" && pwd)/public.key"
GPG_KEY_ID="Pulp QE"

# Export a public key
gpg --armor --export "${GPG_KEY_ID}" > ${PUBLIC_KEY_PATH}

# Create a detached signature
gpg --quiet --batch --homedir ~/.gnupg/ --detach-sign --local-user "${GPG_KEY_ID}" \
   --armor --output ${SIGNATURE_PATH} ${FILE_PATH}

# Check the exit status
STATUS=$?
if [[ ${STATUS} -eq 0 ]]; then
   echo {\"file\": \"${FILE_PATH}\", \"signature\": \"${SIGNATURE_PATH}\", \
       \"key\": \"${PUBLIC_KEY_PATH}\"}
else
   exit ${STATUS}
fi
