# Sign RPM Packages

Sign an RPM Package using a registered RPM signing service.

Currently, only on-upload signing is supported.

## On Upload

!!! tip "New in 3.26.0 (Tech Preview)"

Sign an RPM Package when uploading it to a Repository.

### Pre-requisites

- Have an `RpmPackageSigningService` registered
  (see [here](site:pulp_rpm/docs/admin/guides/add-signing-services/#package-signing)).
- Have the V4 fingerprint of the key you want to use. The key should be accessible by the SigningService you are using.

### Instructions

1. Configure a Repository to enable signing.
    - Both `package_signing_service` and `package_signing_fingerprint` must be set.
    - If they are set, any package upload to the Repository will be signed by the service.
2. Upload a Package to this Repository.

### Example

```bash
# Create a Repository w/ required params
http POST $API_ROOT/repositories/rpm/rpm \
  name="MyRepo" \
  package_signing_service=$SIGNING_SERVICE_HREF \
  package_signing_fingerprint=$SIGNING_FINGERPRINT

# Upload a package
pulp rpm content upload \
  --repository ${REPOSITORY} \
  --file ${FILE}
```

### Known Limitations

**Traffic overhead**: The signing of a package should happen inside of a Pulp worker.
  [By design](site:pulpcore/docs/dev/learn/plugin-concepts/#tasks),
  Pulp needs to temporarily commit the file to the default backend storage in order to make the Uploaded File available to the tasking system.
  This implies in some extra traffic, compared to a scenario where a task could process the file directly.

**No sign tracking**: We do not track signing information of a package.

For extra context, see discussion [here](https://github.com/pulp/pulp_rpm/issues/2986).
