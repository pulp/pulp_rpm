# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
import logging


logger = logging.getLogger(__name__)


def perform_sync(repo, sync_conduit, config):
    """
    Perform the sync operation accoring to the config for the given repo, and return a report. The
    sync progress will be reported through the sync_conduit.

    :rtype: pulp.plugins.model.SyncReport
    """
    progress_report = SyncProgressReport(sync_conduit)

    repo_metadata = _parse_metadata()
    _import_isos()


def _import_isos():
    """
    This does the meat of the work of downloading the ISOs, saving them in the database, and putting
    them in the correct places on the filesystem.
    """
    raise NotImplementedError()


# TODO: Fill out the rtype with something
def _parse_metadata():
    """
    Retrieve and parse the PULP_METADATA file from the repository.

    :return: All the Metadatas!
    :rtype:
    """
    return TheMetadatas
