"""
Contains option definitions for RPM repository configuration and update, pulled
out of the repo commands module itself to keep it from becoming unwieldy.
"""

from gettext import gettext as _

from okaara import parsers
from pulp.client.extensions.extensions import PulpCliOption, PulpCliOptionGroup

from pulp_rpm.common import ids


# Used to validate user entered skip types
VALID_SKIP_TYPES = [ids.TYPE_ID_RPM, ids.TYPE_ID_DRPM, ids.TYPE_ID_DISTRO, ids.TYPE_ID_ERRATA]


def parse_skip_types(t):
    """
    The user-entered value is comma separated and will be the full list of
    types to skip; there is no concept of a diff.

    :param t: user entered value or None
    """
    if t in (None, ''):
        # Returning t itself is important. If it's None, it's an unspecified parameter
        # and should be ignored. If it's an empty string, it's the unset convention,
        # which is translated into a removal later in the parsing.
        return t

    parsed = t.split(',')
    parsed = [p.strip() for p in parsed]

    unmatched = [p for p in parsed if p not in VALID_SKIP_TYPES]
    if len(unmatched) > 0:
        msg = _('Types must be a comma-separated list using only the following values: %(t)s')
        msg = msg % {'t': ', '.join(VALID_SKIP_TYPES)}
        raise ValueError(msg)

    return parsed

# group names
NAME_PUBLISHING = _('Publishing')
NAME_AUTH = _('Consumer Authentication')

ALL_GROUP_NAMES = (NAME_PUBLISHING, NAME_AUTH)

# synchronization options
d = _('comma-separated list of types to omit when synchronizing, if not '
      'specified all types will be synchronized; valid values are: %(t)s')
d = d % {'t': ', '.join(VALID_SKIP_TYPES)}
OPT_SKIP = PulpCliOption('--skip', d, required=False, parse_func=parse_skip_types)

# publish options
d = _('if "true", on each successful sync the repository will automatically be '
      'published on the configured protocols; if "false" synchronized content '
      'will only be available after manually publishing the repository; '
      'defaults to "true"')
OPT_AUTO_PUBLISH = PulpCliOption('--auto-publish', d, required=False,
                                 parse_func=parsers.parse_boolean)

d = _(
    'relative path the repository will be served from. Only alphanumeric characters, '
    'forward slashes, underscores '
    'and dashes are allowed. It defaults to the relative path of the feed URL')
OPT_RELATIVE_URL = PulpCliOption('--relative-url', d, required=False)

d = _('if "true", the repository will be served over HTTP; defaults to false')
OPT_SERVE_HTTP = PulpCliOption('--serve-http', d, required=False, parse_func=parsers.parse_boolean)

d = _('if "true", the repository will be served over HTTPS; defaults to true')
OPT_SERVE_HTTPS = PulpCliOption('--serve-https', d, required=False,
                                parse_func=parsers.parse_boolean)

d = _('type of checksum to use during metadata generation')
OPT_CHECKSUM_TYPE = PulpCliOption('--checksum-type', d, required=False)

d = _('GPG key used to sign and verify packages in the repository')
OPT_GPG_KEY = PulpCliOption('--gpg-key', d, required=False)

d = _('if "true", sqlite files will be generated for the repository metadata during publish')
OPT_GENERATE_SQLITE = PulpCliOption('--generate-sqlite', d, required=False,
                                    parse_func=parsers.parse_boolean)

d = _('if "true", static HTML files will be generated during publish for the fast browsing of '
      'the repository')
OPT_REPOVIEW = PulpCliOption('--repoview', d, required=False,
                             parse_func=parsers.parse_boolean)

# publish security options
d = _('full path to the CA certificate that signed the repository hosts\'s SSL '
      'certificate when serving over HTTPS')
OPT_HOST_CA = PulpCliOption('--host-ca', d, required=False)

d = _('full path to the CA certificate that should be used to verify client '
      'authentication certificates; setting this turns on client '
      'authentication for the repository')
OPT_AUTH_CA = PulpCliOption('--auth-ca', d, required=False)

d = _('full path to the entitlement certificate that will be given to bound '
      'consumers to grant access to this repository')
OPT_AUTH_CERT = PulpCliOption('--auth-cert', d, required=False)


def add_distributor_config_to_command(command):
    publish_group = PulpCliOptionGroup(NAME_PUBLISHING)
    repo_auth_group = PulpCliOptionGroup(NAME_AUTH)

    # The server-side APIs don't allow this to be updated, so hide it as an
    # option entirely; RPM repos are always published automatically with our
    # CLI until we clean that up. jdob, Sept 24, 2012
    # publish_group.add_option(OPT_AUTO_PUBLISH)

    publish_group.add_option(OPT_RELATIVE_URL)
    publish_group.add_option(OPT_SERVE_HTTP)
    publish_group.add_option(OPT_SERVE_HTTPS)
    publish_group.add_option(OPT_CHECKSUM_TYPE)
    publish_group.add_option(OPT_GPG_KEY)
    publish_group.add_option(OPT_GENERATE_SQLITE)
    publish_group.add_option(OPT_REPOVIEW)

    # Order added indicates order in usage, so pay attention to this order when
    # dorking with it to make sure it makes sense
    command.add_option_group(publish_group)
    command.add_option_group(repo_auth_group)

    # Publish Security Options
    repo_auth_group.add_option(OPT_HOST_CA)
    repo_auth_group.add_option(OPT_AUTH_CA)
    repo_auth_group.add_option(OPT_AUTH_CERT)
