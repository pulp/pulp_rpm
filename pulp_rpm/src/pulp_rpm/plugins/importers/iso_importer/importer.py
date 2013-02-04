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

from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp.plugins.importer import Importer

from pulp_rpm.common import ids
from pulp_rpm.plugins.importers.iso_importer import configuration, sync

logger = logging.getLogger(__name__)


def entry_point():
    """
    This method allows us to announce this importer to the Pulp Platform.

    :return: importer class as its config
    :rtype:  tuple
    """
    return ISOImporter, {}


class ISOImporter(Importer):
    """
    All methods that are missing docstrings are documented in the Importer superclass.
    """
    def cancel_sync_repo(self, call_request, call_report):
        self.iso_sync.cancel_sync()

    def import_units(self, source_repo, dest_repo, import_conduit, config, units=None):
        """
        Import content units into the given repository. This method will be
        called in a number of different situations:
         * A user is attempting to copy a content unit from one repository
           into the repository that uses this importer
         * A user is attempting to add an orphaned unit into a repository.

        The units argument is optional. If None, all units in the source
        repository should be imported. The conduit is used to query for those
        units. If specified, only the units indicated should be imported (this
        is the case where the caller passed a filter to Pulp).

        @param source_repo:    metadata describing the repository containing the
                               units to import
        @type  source_repo:    L{pulp.server.plugins.model.Repository}

        @param dest_repo:      metadata describing the repository to import units
                               into
        @type  dest_repo:      L{pulp.server.plugins.model.Repository}

        @param import_conduit: provides access to relevant Pulp functionality
        @type  import_conduit: L{pulp.server.conduits.unit_import.ImportUnitConduit}

        @param config:         plugin configuration
        @type  config:         L{pulp.server.plugins.config.PluginCallConfiguration}

        @param units:          optional list of pre-filtered units to import
        @type  units:          list of L{pulp.server.plugins.model.Unit}
        """
        if units is None:
            criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_ISO])
            units = import_conduit.get_source_units(criteria=criteria)

        for u in units:
            import_conduit.associate_unit(u)


    @classmethod
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_IMPORTER_ISO,
            'display_name': 'ISO Importer',
            'types': [ids.TYPE_ID_ISO]
        }

    def sync_repo(self, repo, sync_conduit, config):
        self.iso_sync = sync.ISOSyncRun()
        report = self.iso_sync.perform_sync(repo, sync_conduit, config)
        self.iso_sync = None
        return report

    def upload_unit(self, repo, type_id, unit_key, metadata, file_path, conduit, config):
        raise NotImplementedError()

    def validate_config(self, repo, config, related_repos):
        return configuration.validate(config)
