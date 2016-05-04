TYPE_ID_DISTRIBUTOR_EXPORT = "export_distributor"
TYPE_ID_DISTRIBUTOR_GROUP_EXPORT = 'group_export_distributor'
TYPE_ID_DISTRIBUTOR_ISO = "iso_distributor"
TYPE_ID_DISTRIBUTOR_YUM = "yum_distributor"
TYPE_ID_IMPORTER_ISO = "iso_importer"
TYPE_ID_IMPORTER_YUM = "yum_importer"

# The server will use the type ID as the importer ID, but have it as a separate
# constant in case that changes
YUM_IMPORTER_ID = TYPE_ID_IMPORTER_YUM

# Set when the distributor is added to the repo and later to refer to it specifically
YUM_DISTRIBUTOR_ID = TYPE_ID_DISTRIBUTOR_YUM

# Set when the distributor is added to the repo and later to refer to it specifically
EXPORT_DISTRIBUTOR_ID = 'export_distributor'

TYPE_ID_ISO = 'iso'
TYPE_ID_RPM = 'rpm'
TYPE_ID_SRPM = 'srpm'
UNIT_KEY_RPM = (
    "name", "epoch", "version", "release", "arch", "checksum", "checksumtype")

TYPE_ID_ERRATA = 'erratum'
UNIT_KEY_ERRATA = ("id",)

METADATA_ERRATA = (
    "title", "description", "version", "release", "type", "status", "updated",
    "issued", "severity", "references", "pkglist", "rights", "summary",
    "solution", "from_str", "pushcount", "reboot_suggested")

TYPE_ID_PKG_GROUP = 'package_group'
TYPE_ID_PKG_CATEGORY = 'package_category'
TYPE_ID_PKG_ENVIRONMENT = 'package_environment'
TYPE_ID_PKG_LANGPACKS = 'package_langpacks'

# We are adding the 'repo_id' to unit_key for each group/category
# to ensure that each group/category is defined only for that given repo_id
# We do not want to allow sharing a single group or category between repos.
UNIT_KEY_PKG_GROUP = ("id", "repo_id")
METADATA_PKG_GROUP = (
    "name", "description", "default", "user_visible", "langonly", "display_order",
    "mandatory_package_names", "conditional_package_names",
    "optional_package_names", "default_package_names",
    "translated_description", "translated_name")

UNIT_KEY_PKG_CATEGORY = ("id", "repo_id")
METADATA_PKG_CATEGORY = (
    "name", "description", "display_order", "translated_name",
    "translated_description",
    "packagegroupids")

TYPE_ID_DISTRO = 'distribution'
UNIT_KEY_DISTRO = ("id", "family", "variant", "version", "arch")
METADATA_DISTRO = ("files",)

TYPE_ID_DRPM = 'drpm'
UNIT_KEY_DRPM = (
    "epoch", "version", "release", "filename", "checksum", "checksumtype")

METADATA_DRPM = ("size", "sequence", "new_package", "relativepath")

TYPE_ID_YUM_REPO_METADATA_FILE = 'yum_repo_metadata_file'

# These types don't have support for the query-param auth token yet
QUERY_AUTH_TOKEN_UNSUPPORTED = (TYPE_ID_ISO, TYPE_ID_ERRATA, TYPE_ID_DISTRO)
