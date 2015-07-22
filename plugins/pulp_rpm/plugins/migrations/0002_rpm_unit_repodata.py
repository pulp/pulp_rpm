# -*- coding: utf-8 -*-
# Migration script for existing rpm units to include repodata

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
