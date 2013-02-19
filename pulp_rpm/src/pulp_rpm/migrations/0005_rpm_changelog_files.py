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

import os
import logging
import rpmUtils
from createrepo import yumbased

from pulp.server.managers.content.query import ContentQueryManager
from pulp_rpm.yum_plugin import util

_log = logging.getLogger('pulp')

def _migrate_rpm_unit_changelog_files():
    """
    Looks up rpm unit collection in the db and computes the changelog and filelist data
    if not already available; If the package path is missing,
    the fields are defaulted to empty list.
    """
    query_manager = ContentQueryManager()
    collection = query_manager.get_content_unit_collection(type_id="rpm")
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    for rpm_unit in collection.find():
        pkg_path = rpm_unit['_storage_path']
        if not os.path.exists(pkg_path):
            # if pkg doesnt exist, we cant get the pkg object, continue
            continue
        po = yumbased.CreateRepoPackage(ts, pkg_path)
        for key in ["changelog", "filelist", "files"]:
            if key not in rpm_unit or not rpm_unit[key]:
                if key == "changelog":
                    data = map(lambda x: __encode_changelog(x), po[key])
                else:
                    data = getattr(po, key)
                rpm_unit[key] = data
                _log.debug("missing pkg: %s ; key %s" % (rpm_unit, key))
        collection.save(rpm_unit, safe=True)
    _log.info("Migrated rpms to include rpm changelog and filelist metadata")

def __encode_changelog(changelog_tuple):
    timestamp, email, description = changelog_tuple
    email = util.encode_string_to_utf8(email)
    description = util.encode_string_to_utf8(description)
    return (timestamp, email, description)

def migrate(*args, **kwargs):
    _migrate_rpm_unit_changelog_files()
