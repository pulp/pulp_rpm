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

from gettext import gettext as _
import logging
import shutil

from pulp.plugins.importer import Importer

from pulp_rpm.common import ids, models
from pulp_rpm.plugins.importers.yum import sync, associate


_LOGGER = logging.getLogger(__name__)


def entry_point():
    """
    Entry point that pulp platform uses to load the importer
    :return: importer class and its config
    :rtype:  Importer, {}
    """
    return YumImporter, {}


class YumImporter(Importer):
    @classmethod
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_IMPORTER_YUM,
            'display_name': _('Yum Importer'),
            'types': [
                ids.TYPE_ID_DISTRO, ids.TYPE_ID_DRPM, ids.TYPE_ID_ERRATA,
                ids.TYPE_ID_PKG_GROUP, ids.TYPE_ID_PKG_CATEGORY, ids.TYPE_ID_RPM,
                ids.TYPE_ID_SRPM,
            ]
        }

    def validate_config(self, repo, config, related_repos):
        return True, None

    def import_units(self, source_repo, dest_repo, import_conduit, config, units=None):
        return associate.associate(source_repo, dest_repo, import_conduit, config, units)

    def upload_unit(self, repo, type_id, unit_key, metadata, file_path, conduit, config):
        rpm = models.RPM(metadata=metadata, **unit_key)
        unit = conduit.init_unit(type_id, rpm.unit_key, rpm.metadata, rpm.relative_path)
        try:
            shutil.copy(file_path, unit.storage_path)
        except IOError:
            # do something sensible here
            raise

        conduit.save_unit(unit)

    def sync_repo(self, repo, sync_conduit, call_config):
        return sync.RepoSync(repo, sync_conduit, call_config).run()
