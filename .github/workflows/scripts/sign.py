from pulpcore.plugin.models import AsciiArmoredDetachedSigningService


with open("GPG-KEY-pulp-qe") as key:
    AsciiArmoredDetachedSigningService.objects.create(
        name="sign-metadata",
        public_key=key.read(),
        pubkey_fingerprint="6EDF301256480B9B801EBA3D05A5E6DA269D9D98",
        script="/root/sign-metadata.sh",
    )
