# Register Signing Services

Create a `SigningService` for signing RPM metadata (`repomd.xml`) or RPM Packages.

## Metadata Signing

RPM metadata signing uses detached signature, which is already provided by pulpcore.
To register such a service, follow the general instructions [in pulpcore](site:pulpcore/docs/admin/guides/sign-metadata/).

## Package Signing

!!! tip "New in 3.26.0 (Tech Preview)"

Package signing is not detached as metadata signing, so it uses a different type of `SigningService`.
Nevertheless, the process of registering is very similar.

### Pre-Requisites

- Get familiar with the general SigningService registration [here](site:pulpcore/docs/admin/guides/sign-metadata/).

### Instructions

1. Create a signing script capable of signing an RPM Package.
    - The script receives a file path as its first argument.
    - The script should return a json-formatted output. No signature is required, since its embedded.
      ```json
      {"file": "filename"}
      ```
1. Register it with `pulpcore-manager add-signing-service`.
    - The `--class` should be `rpm:RpmPackageSigningService`.
    - The key provided here serves only for validating the script.
      The signing fingerprint is provided dynamically, as [on upload signing](site:pulp_rpm/docs/user/guides/sign-packages/#on-upload).
1. Retrieve the signing service for usage.

### Example

Write a signing script.
The following example is roughly what we use for testing.

```bash title="package-signing-script.sh"
#!/usr/bin/env bash

# Input provided to the script
FILE_PATH=$1
FINGERPRINT="${PULP_SIGNING_KEY_FINGERPRINT}"

# Specific signing logic
GPG_HOME=${HOME}/.gnupg
GPG_BIN=/usr/bin/gpg
rpm \
    --define "_signature gpg" \
    --define "_gpg_path ${GPG_HOME}" \
    --define "_gpg_name ${FINGERPRINT}" \
    --define "_gpgbin ${GPG_BIN}" \
    --addsign "${FILE_PATH}" 1> /dev/null

# Output
STATUS=$?
if [[ ${STATUS} -eq 0 ]]; then
   echo {\"rpm_package\": \"${FILE_PATH}\"}
else
   exit ${STATUS}
fi
```

Register the signing service and retrieve information about it.

```bash
pulpcore-manager add-signing-service \
  "SimpleRpmSigningService" \
  ${SCRIPT_ABS_FILENAME} \
  ${KEYID} \
  --class "rpm:RpmPackageSigningService"

pulp signing-service show --name "SimpleRpmSigningService"
```



