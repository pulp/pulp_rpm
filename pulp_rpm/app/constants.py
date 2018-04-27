from types import SimpleNamespace

CHECKSUM_TYPES = SimpleNamespace(
    UNKNOWN='unknown',
    MD5='md5',
    SHA='sha1',  # compatibility nickname from original createrepo
    SHA1='sha1',
    SHA224='sha224',
    SHA256='sha256',
    SHA384='sha384',
    SHA512='sha512'
)

# The same as above, but in a format that choice fields can use
CHECKSUM_CHOICES = (
    (CHECKSUM_TYPES.UNKNOWN, CHECKSUM_TYPES.UNKNOWN),
    (CHECKSUM_TYPES.MD5, CHECKSUM_TYPES.MD5),
    (CHECKSUM_TYPES.SHA, CHECKSUM_TYPES.SHA),
    (CHECKSUM_TYPES.SHA1, CHECKSUM_TYPES.SHA1),
    (CHECKSUM_TYPES.SHA224, CHECKSUM_TYPES.SHA224),
    (CHECKSUM_TYPES.SHA256, CHECKSUM_TYPES.SHA256),
    (CHECKSUM_TYPES.SHA384, CHECKSUM_TYPES.SHA384),
    (CHECKSUM_TYPES.SHA512, CHECKSUM_TYPES.SHA512)
)
