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

CREATEREPO_PACKAGE_ATTRS = SimpleNamespace(
    ARCH='arch',
    CHANGELOGS='changelogs',
    CHECKSUM_TYPE='checksum_type',
    CONFLICTS='conflicts',
    DESCRIPTION='description',
    ENHANCES='enhances',
    EPOCH='epoch',
    FILES='files',
    LOCATION_BASE='location_base',
    LOCATION_HREF='location_href',
    NAME='name',
    OBSOLETES='obsoletes',
    PKGID='pkgId',
    PROVIDES='provides',
    RECOMMENDS='recommends',
    RELEASE='release',
    REQUIRES='requires',
    RPM_BUILDHOST='rpm_buildhost',
    RPM_GROUP='rpm_group',
    RPM_HEADER_END='rpm_header_end',
    RPM_HEADER_START='rpm_header_start',
    RPM_LICENSE='rpm_license',
    RPM_PACKAGER='rpm_packager',
    RPM_SOURCERPM='rpm_sourcerpm',
    RPM_VENDOR='rpm_vendor',
    SIZE_ARCHIVE='size_archive',
    SIZE_INSTALLED='size_installed',
    SIZE_PACKAGE='size_package',
    SUGGESTS='suggests',
    SUMMARY='summary',
    SUPPLEMENTS='supplements',
    TIME_BUILD='time_build',
    TIME_FILE='time_file',
    URL='url',
    VERSION='version'
)

PACKAGE_REPODATA = ['primary', 'filelists', 'other']
UPDATE_REPODATA = ['updateinfo']
