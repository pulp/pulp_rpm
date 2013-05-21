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

from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.managers.repo.unit_association import OWNER_TYPE_IMPORTER

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd import packages, primary, presto, updateinfo, group


def remove_missing_rpms(metadata_files, conduit):
    remote_named_tuples = get_remote_units(metadata_files, primary.METADATA_FILE_NAME, models.RPM,
                                            primary.PACKAGE_TAG, primary.process_package_element)
    remove_missing_units(metadata_files, conduit, models.RPM, remote_named_tuples)


def remove_missing_drpms(metadata_files, conduit):
    remote_named_tuples = get_remote_units(metadata_files, presto.METADATA_FILE_NAME, models.DRPM,
                                            presto.PACKAGE_TAG, presto.process_package_element)
    remove_missing_units(metadata_files, conduit, models.DRPM, remote_named_tuples)


def remove_missing_errata(metadata_files, conduit):
    remote_named_tuples = get_remote_units(metadata_files, updateinfo.METADATA_FILE_NAME, models.Errata,
                                           updateinfo.PACKAGE_TAG, updateinfo.process_package_element)
    remove_missing_units(metadata_files, conduit, models.Errata, remote_named_tuples)


def remove_missing_groups(metadata_files, conduit):
    remote_named_tuples = get_remote_units(metadata_files, group.METADATA_FILE_NAME, models.PackageGroup,
                                           group.GROUP_TAG, group.process_group_element)
    remove_missing_units(metadata_files, conduit, models.PackageGroup, remote_named_tuples)


def remove_missing_categories(metadata_files, conduit):
    remote_named_tuples = get_remote_units(metadata_files, group.METADATA_FILE_NAME, models.PackageCategory,
                                           group.CATEGORY_TAG, group.process_category_element)
    remove_missing_units(metadata_files, conduit, models.PackageCategory, remote_named_tuples)


def remove_missing_units(metadata_files, conduit, model, remote_named_tuples):
    for unit in get_existing_units(model, conduit.get_units):
        named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
        try:
            # if we found it, remove it so we can free memory as we go along
            remote_named_tuples.remove(named_tuple)
        except KeyError:
            conduit.remove_unit(unit)


def get_existing_units(model, unit_search_method):
    assoc_filters = {'owner_type': OWNER_TYPE_IMPORTER}
    criteria = UnitAssociationCriteria([model.TYPE],
                                       unit_fields=model.UNIT_KEY_NAMES,
                                       association_filters=assoc_filters)
    return unit_search_method(criteria)


def get_remote_units(metadata_files, file_name, model, tag, process_func):
    remote_named_tuples = set()
    file_handle = metadata_files.get_metadata_file_handle(file_name)
    if file_handle is None:
        return set()
    try:
        package_info_generator = packages.package_list_generator(file_handle,
                                                                 tag,
                                                                 process_func)

        for model in package_info_generator:
            named_tuple = model.as_named_tuple
            remote_named_tuples.add(named_tuple)

    finally:
        file_handle.close()
    return remote_named_tuples
