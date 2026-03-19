Signing fingerprints now use a versioned prefix format (e.g. ``v4:<hex>``, ``keyid:<hex>``) for
``package_signing_fingerprint`` on repositories and ``signing_keys`` on packages. The repository
serializer validates the format on input.
