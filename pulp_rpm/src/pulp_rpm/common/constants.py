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
REPO_NOTE_KEY = '_repo-type' # needs to be standard across extensions
REPO_NOTE_RPM = 'rpm-repo'

PUBLISHED_DISTRIBUTION_FILES_KEY = 'published_distributions'

# Importer configuration key names
CONFIG_FEED_URL        = 'feed_url'
CONFIG_MAX_SPEED       = 'max_speed'
CONFIG_NUM_THREADS     = 'num_threads'
CONFIG_PROXY_PASSWORD  = 'proxy_password'
CONFIG_PROXY_PORT      = 'proxy_port'
CONFIG_PROXY_URL       = 'proxy_url'
CONFIG_PROXY_USER      = 'proxy_user'
CONFIG_SSL_CA_CERT     = 'ssl_ca_cert'
CONFIG_SSL_CLIENT_CERT = 'ssl_client_cert'
CONFIG_SSL_CLIENT_KEY  = 'ssl_client_key'

# Distributor configuration key names
CONFIG_SERVE_HTTP      = 'serve_http'
CONFIG_SERVE_HTTPS     = 'serve_https'

ISO_HTTP_DIR = "/var/lib/pulp/published/http/isos"
ISO_HTTPS_DIR = "/var/lib/pulp/published/https/isos"
