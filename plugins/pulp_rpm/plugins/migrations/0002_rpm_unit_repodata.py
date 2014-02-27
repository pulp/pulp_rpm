# -*- coding: utf-8 -*-
# Migration script for existing rpm units to include repodata
#
# Copyright © 2010-2012 Red Hat, Inc.
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

from pulp.server.managers.content.query import ContentQueryManager
from pulp_rpm.yum_plugin import metadata

_log = logging.getLogger('pulp')

def _migrate_rpm_unit_repodata():
    """
    Looks up rpm unit collection in the db and computes the repodata if not already available;
    If the package path is missing, the repodata if stored as an empty dict.
    """
    query_manager = ContentQueryManager()
    collection = query_manager.get_content_unit_collection(type_id="rpm")
    for rpm_unit in collection.find():
        if "repodata" not in rpm_unit or not rpm_unit["repodata"]:
            # if repodata is not in the schema or repodata is empty
            rpm_unit["repodata"] = metadata.get_package_xml(rpm_unit['_storage_path'])
            collection.save(rpm_unit, safe=True)
    _log.info("Migrated rpms to include rpm metadata")

def migrate(*args, **kwargs):
    _migrate_rpm_unit_repodata()
