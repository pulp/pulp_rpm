# -*- coding: utf-8 -*-
# Migration script for existing rpm units to include repodata

import logging
import os

from createrepo import yumbased
from pulp.server.db import connection
from pulp.server.managers.content.query import ContentQueryManager
import rpmUtils.transaction

from pulp_rpm.yum_plugin import util


_LOGGER = logging.getLogger('pulp_rpm.plugins.migrations.0005')


def _migrate_unit(rpm_unit, ts, collection):
    pkg_path = rpm_unit['_storage_path']
    if not os.path.exists(pkg_path):
        # if pkg doesnt exist, we cant get the pkg object, continue
        return
    po = yumbased.CreateRepoPackage(ts, pkg_path)
    for key in ["changelog", "filelist", "files"]:
        if key not in rpm_unit or not rpm_unit[key]:
            value = getattr(po, key)
            if key == "changelog":
                data = map(_decode_changelog, value)
            elif key == "filelist":
                data = map(util.string_to_unicode, value)
            elif key == "files":
                data = _decode_files(value)
            rpm_unit[key] = data
    collection.save(rpm_unit, safe=True)


def _decode_changelog(changelog_tuple):
    timestamp, email, description = changelog_tuple
    email = util.string_to_unicode(email)
    description = util.string_to_unicode(description)
    return timestamp, email, description


def _decode_files(data):
    """
    Walk this data structure, turning strings into unicode objects along the way

    :param data:    dictionary where keys are 'ghost', 'dir', and 'file'; and
                    values are lists of filesystem paths
    :type  data:    dict

    :return:    reference to original dictionary
    :rtype:     dict
    """
    for key, value in data.iteritems():
        if isinstance(value, (list, tuple)):
            data[key] = map(util.string_to_unicode, value)
    return data


def migrate(*args, **kwargs):
    """
    Looks up rpm unit collection in the db and computes the changelog and filelist data
    if not already available; If the package path is missing,
    the fields are defaulted to empty list.
    """
    query_manager = ContentQueryManager()
    collection = query_manager.get_content_unit_collection(type_id="rpm")
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    for rpm_unit in collection.find():
        _migrate_unit(rpm_unit, ts, collection)
    _LOGGER.info("Migrated rpms to include rpm changelog and filelist metadata")


if __name__ == '__main__':
    connection.initialize()
    migrate()
