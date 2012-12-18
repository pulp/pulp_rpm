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

# There is no clean way to get the distribution storage location outside of the unit;
# we need this path when initializing grinder so the treeinfo file gets compied and
# symlinked to the right path. Once we have a nicer way of getting this path replace this
DISTRIBUTION_STORAGE_PATH = '/var/lib/pulp/content/distribution/'

# During publish we need to lookup and make sure the treeinfo exists; since the treeinfo
# can be '.treeinfo' or 'treeinfo' (in cdn case) we need to check which one exists
TREE_INFO_LIST = ['.treeinfo', 'treeinfo']
