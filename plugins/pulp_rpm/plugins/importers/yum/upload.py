# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
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
import shutil

from pulp.plugins.model import SyncReport

from pulp_rpm.common import models

_LOGGER = logging.getLogger(__name__)


def upload(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    :param repo: metadata describing the repository
    :type  repo: pulp.plugins.model.Repository

    :param type_id: type of unit being uploaded
    :type  type_id: str

    :param unit_key: identifier for the unit, specified by the user
    :type  unit_key: dict

    :param metadata: any user-specified metadata for the unit
    :type  metadata: dict

    :param file_path: path on the Pulp server's filesystem to the temporary
           location of the uploaded file; may be None in the event that a
           unit is comprised entirely of metadata and has no bits associated
    :type  file_path: str

    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.unit_add.UnitAddConduit

    :param config: plugin configuration for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: report of the details of the sync
    :rtype:  pulp.plugins.model.SyncReport
    """

    model_type = models.TYPE_MAP[type_id]
    # get metadata
    model = model_type(metadata=metadata, **unit_key)
    # init unit
    unit = conduit.init_unit(model.TYPE, model.unit_key, model.metadata, model.relative_path)
    # copy file to destination
    try:
        # TODO: need to create the destination directory?
        shutil.copy(file_path, unit.storage_path)
    except IOError:
        return SyncReport(False, 0, 0, 0, 'failed to copy file', {})

    # save unit
    conduit.save_unit(unit)

    report = SyncReport(True, 1, 0, 0, '', {})
    return report