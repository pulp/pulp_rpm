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

from gettext import gettext as _
import logging

from pulp.plugins.importer import Importer

from pulp_rpm.common import ids

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
        raise NotImplementedError()

    def import_units(self, source_repo, dest_repo, import_conduit, config, units=None):
        raise NotImplementedError()

    @classmethod
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_IMPORTER_ISO,
            'display_name': 'ISO Importer',
            'types': [ids.TYPE_ID_ISO]
        }

    def sync_repo(self, repo, sync_conduit, config):
        sync.perform_sync(repo, sync_conduit, config)

    def upload_unit(self, repo, type_id, unit_key, metadata, file_path, conduit, config):
        raise NotImplementedError()

    def validate_config(self, repo, config, related_repos):
        raise NotImplementedError()
