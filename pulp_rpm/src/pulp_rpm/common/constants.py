# Copyright (c) 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

# -- progress states ----------------------------------------------------------

# These are used by the RPM reports, but not by the ISO reports (since those use their own state machines)
STATE_NOT_STARTED = 'NOT_STARTED'
STATE_RUNNING = 'IN_PROGRESS'
STATE_COMPLETE = 'FINISHED'
STATE_FAILED = 'FAILED'
STATE_SKIPPED = 'SKIPPED'
STATE_CANCELLED = 'CANCELLED'

COMPLETE_STATES = (STATE_COMPLETE, STATE_FAILED, STATE_SKIPPED)

# Codes included in the progress report for each unit to identify what went wrong
ERROR_SIZE_VERIFICATION = 'size_mismatch'
ERROR_CHECKSUM_VERIFICATION = 'checksum_mismatch'
ERROR_CHECKSUM_TYPE_UNKNOWN = 'checksum_type_unknown'

# Standard keywords for progress reports to include
PROGRESS_STATE_KEY = 'state'
PROGRESS_NUM_SUCCESS_KEY = 'num_success'
PROGRESS_NUM_ERROR_KEY = 'num_error'
PROGRESS_ITEMS_LEFT_KEY = 'items_left'
PROGRESS_ITEMS_TOTAL_KEY = 'items_total'
PROGRESS_ERROR_DETAILS_KEY = 'error_details'

# Progress report keywords used in the group export distributor progress report
PROGRESS_REPOS_KEYWORD = 'repositories'
PROGRESS_ISOS_KEYWORD = 'isos'
PROGRESS_PUBLISH_HTTP = 'publish_http'
PROGRESS_PUBLISH_HTTPS = 'publish_https'

# Progress report keywords used by the export distributor progress report
PROGRESS_METADATA_KEYWORD = 'metadata'

# -- yum distributor publish progress -----------------------------------------

PUBLISH_STATES = (STATE_NOT_STARTED, STATE_RUNNING, STATE_SKIPPED,
                  STATE_COMPLETE, STATE_FAILED, STATE_CANCELLED)

PUBLISH_RPMS_STEP = 'rpms'
PUBLISH_DELTA_RPMS_STEP = 'drpms'
PUBLISH_ERRATA_STEP = 'errata'
PUBLISH_COMPS_STEP = 'comps'
PUBLISH_PACKAGE_GROUPS_STEP = 'package_groups'
PUBLISH_PACKAGE_CATEGORIES_STEP = 'package_categories'
PUBLISH_DISTRIBUTION_STEP = 'distribution'
PUBLISH_METADATA_STEP = 'metadata'
PUBLISH_OVER_HTTP_STEP = 'publish_over_http'
PUBLISH_OVER_HTTPS_STEP = 'publish_over_https'

PUBLISH_STEPS = (PUBLISH_RPMS_STEP, PUBLISH_DELTA_RPMS_STEP, PUBLISH_ERRATA_STEP,
                 PUBLISH_COMPS_STEP, PUBLISH_DISTRIBUTION_STEP, PUBLISH_METADATA_STEP,
                 PUBLISH_OVER_HTTP_STEP, PUBLISH_OVER_HTTPS_STEP)

PROGRESS_TOTAL_KEY = 'total'
PROGRESS_PROCESSED_KEY = 'processed'
PROGRESS_SUCCESSES_KEY = 'successes'
PROGRESS_FAILURES_KEY = 'failures'

PUBLISH_REPORT_KEYS = (PROGRESS_STATE_KEY, PROGRESS_TOTAL_KEY, PROGRESS_PROCESSED_KEY,
                       PROGRESS_SUCCESSES_KEY, PROGRESS_FAILURES_KEY, PROGRESS_ERROR_DETAILS_KEY)

# -- configuration ------------------------------------------------------------

# Used as a note on a repository to indicate it is a Puppet repository
REPO_NOTE_RPM = 'rpm-repo'
REPO_NOTE_ISO = 'iso-repo'

PUBLISHED_DISTRIBUTION_FILES_KEY = 'published_distributions'

# The default number of threads to be used with downloading ISOs. We should convert the RPM code to
# use this same value.
CONFIG_MAX_DOWNLOADS_DEFAULT        = 5
# By default, we should use the CA certificate to validate the remote host
CONFIG_SSL_VALIDATION_DEFAULT       = True
# By default, do not remove units that are in the repo that are not in the feed
CONFIG_UNITS_REMOVE_MISSING_DEFAULT = False
# By default, lets validate units
CONFIG_VALIDATE_DEFAULT             = True

# Distributor configuration key names
CONFIG_SERVE_HTTP          = 'serve_http'
CONFIG_SERVE_HTTP_DEFAULT  = False
CONFIG_SERVE_HTTPS         = 'serve_https'
CONFIG_SERVE_HTTPS_DEFAULT = True
CONFIG_KEY_CHECKSUM_TYPE = 'checksum_type'
CONFIG_DEFAULT_CHECKSUM = 'sha256'

# list of types to skip at sync time
CONFIG_SKIP = 'type_skip_list'

# This is the CA that we should verify client entitlement certificates with. If it is set, and protected repos
# are enabled serverwide, we will protect the repo with this cert over SSL. If it is unset, no repo protection
# will be configured. This option is currently only used by the ISO distributor.
CONFIG_SSL_AUTH_CA_CERT = 'ssl_auth_ca_cert'

# Copy operation config
CONFIG_RECURSIVE = 'recursive'

ISO_HTTP_DIR = "/var/lib/pulp/published/http/isos"
ISO_HTTPS_DIR = "/var/lib/pulp/published/https/isos"

# There is no clean way to get the distribution storage location outside of the unit;
# we need this path when initializing.  Once we have a nicer way of getting this path replace this
DISTRIBUTION_STORAGE_PATH = '/var/lib/pulp/content/distribution/'

# During publish we need to lookup and make sure the treeinfo exists; since the treeinfo
# can be '.treeinfo' or 'treeinfo' (in cdn case) we need to check which one exists
TREE_INFO_LIST = ['.treeinfo', 'treeinfo']

# Configuration constants for export distributors
PUBLISH_HTTP_KEYWORD = 'http'
PUBLISH_HTTPS_KEYWORD = 'https'
EXPORT_REQUIRED_CONFIG_KEYS = (PUBLISH_HTTP_KEYWORD, PUBLISH_HTTPS_KEYWORD)

END_DATE_KEYWORD = 'end_date'
EXPORT_DIRECTORY_KEYWORD = 'export_dir'
ISO_PREFIX_KEYWORD = 'iso_prefix'
ISO_SIZE_KEYWORD = 'iso_size'
SKIP_KEYWORD = 'skip'
START_DATE_KEYWORD = 'start_date'
EXPORT_OPTIONAL_CONFIG_KEYS = (END_DATE_KEYWORD, ISO_PREFIX_KEYWORD, SKIP_KEYWORD,
                               EXPORT_DIRECTORY_KEYWORD, START_DATE_KEYWORD, ISO_SIZE_KEYWORD)

EXPORT_HTTP_DIR = '/var/lib/pulp/published/http/exports/repo'
EXPORT_HTTPS_DIR = '/var/lib/pulp/published/https/exports/repo'

GROUP_EXPORT_HTTP_DIR = '/var/lib/pulp/published/http/exports/repo_group'
GROUP_EXPORT_HTTPS_DIR = '/var/lib/pulp/published/https/exports/repo_group'

# Keys used for reading & writing messages from server to clinet
UNIT_KEY = 'unit_key'
ERROR_CODE = 'error_code'
NAME = 'name'
CHECKSUM_TYPE = 'checksum_type'
ACCEPTED_CHECKSUM_TYPES = 'accepted_checksum_types'
ERROR_KEY_CHECKSUM_EXPECTED = 'expected_checksum'
ERROR_KEY_CHECKSUM_ACTUAL = 'actual_checksum'
ERROR_KEY_EXPECTED_SIZE = 'expected_size'
ERROR_KEY_ACTUAL_SIZE = 'actual_size'

# Keys used for the scratchpad
SCRATCHPAD_DEFAULT_METADATA_CHECKSUM = 'checksum_type'

# -- extensions ---------------------------------------------------------------

# Number of units to display by name for operations that return a list of
# modules that were acted on, such as copy and remove
DISPLAY_UNITS_THRESHOLD = 100

# Profiler configuration key name
CONFIG_APPLICABILITY_REPORT_STYLE = 'report_style'
APPLICABILITY_REPORT_STYLE_BY_UNITS = 'by_units'
APPLICABILITY_REPORT_STYLE_BY_CONSUMERS = 'by_consumers'

# The path to the repo_auth.conf file
REPO_AUTH_CONFIG_FILE = '/etc/pulp/repo_auth.conf'
