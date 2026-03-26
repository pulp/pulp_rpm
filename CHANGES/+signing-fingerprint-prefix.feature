Signing fingerprints now use a versioned prefix format (e.g. `v4:<hex>`, `keyid:<hex>`) for
`package_signing_fingerprint` on repositories and `signing_keys` on packages. The fingerprint prefix
is passed to the signing script as the `PULP_SIGNING_FINGERPRINT_TYPE` environment variable.
