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

STATE_NOT_STARTED = 'NOT_STARTED'
STATE_RUNNING = 'IN_PROGRESS'
STATE_COMPLETE = 'FINISHED'
STATE_FAILED = 'FAILED'
STATE_SKIPPED = 'SKIPPED'

COMPLETE_STATES = (STATE_COMPLETE, STATE_FAILED, STATE_SKIPPED)

# Used as a note on a repository to indicate it is a Puppet repository
REPO_NOTE_RPM = 'rpm-repo'
REPO_NOTE_ISO = 'iso-repo'

PUBLISHED_DISTRIBUTION_FILES_KEY = 'published_distributions'

# Importer configuration key names
CONFIG_FEED_URL                     = 'feed_url'
CONFIG_MAX_SPEED                    = 'max_speed'
CONFIG_NUM_THREADS                  = 'num_threads'
# The default number of threads to be used with downloading ISOs. We should convert the RPM code to
# use this same value.
CONFIG_NUM_THREADS_DEFAULT          = 5
CONFIG_PROXY_PASSWORD               = 'proxy_password'
CONFIG_PROXY_PORT                   = 'proxy_port'
CONFIG_PROXY_URL                    = 'proxy_url'
CONFIG_PROXY_USER                   = 'proxy_user'
CONFIG_REMOVE_MISSING_UNITS         = 'remove_missing_units'
CONFIG_REMOVE_MISSING_UNITS_DEFAULT = False
CONFIG_SSL_CA_CERT                  = 'ssl_ca_cert'
CONFIG_SSL_CLIENT_CERT              = 'ssl_client_cert'
CONFIG_SSL_CLIENT_KEY               = 'ssl_client_key'
CONFIG_VALIDATE_DOWNLOADS           = 'validate_downloads'
CONFIG_VALIDATE_DOWNLOADS_DEFAULT   = True

# Distributor configuration key names
CONFIG_SERVE_HTTP      = 'serve_http'
CONFIG_SERVE_HTTPS     = 'serve_https'

EXPORT_HTTP_DIR="/var/lib/pulp/published/http/exports"
EXPORT_HTTPS_DIR="/var/lib/pulp/published/https/exports"
ISO_HTTP_DIR = "/var/lib/pulp/published/http/isos"
ISO_HTTPS_DIR = "/var/lib/pulp/published/https/isos"
ISO_MANIFEST_FILENAME = 'PULP_MANIFEST'

# There is no clean way to get the distribution storage location outside of the unit;
# we need this path when initializing grinder so the treeinfo file gets compied and
# symlinked to the right path. Once we have a nicer way of getting this path replace this
DISTRIBUTION_STORAGE_PATH = '/var/lib/pulp/content/distribution/'

# During publish we need to lookup and make sure the treeinfo exists; since the treeinfo
# can be '.treeinfo' or 'treeinfo' (in cdn case) we need to check which one exists
TREE_INFO_LIST = ['.treeinfo', 'treeinfo']

# -- extensions ---------------------------------------------------------------

# Number of units to display by name for operations that return a list of
# modules that were acted on, such as copy and remove
DISPLAY_UNITS_THRESHOLD = 100

# Profiler configuration key name
CONFIG_APPLICABILITY_REPORT_STYLE = 'report_style'
APPLICABILITY_REPORT_STYLE_BY_UNITS = 'by_units'
APPLICABILITY_REPORT_STYLE_BY_CONSUMERS = 'by_consumers'
