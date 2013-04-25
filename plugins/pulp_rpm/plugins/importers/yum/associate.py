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

import copy
import functools
import logging

from pulp.server import managers

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd import existing

_LOGGER = logging.getLogger(__name__)


def associate(source_repo, dest_repo, import_conduit, config, units=None):
    if units is None:
        # this might use a lot of RAM since RPMs tend to have lots of metadata
        units = import_conduit.get_source_units()

    associated_units = [_associate_unit(dest_repo, import_conduit, unit) for unit in units]
    units = None

    groups, rpm_names, rpm_unit_keys = decide_what_to_get(associated_units)
    rpms_to_copy = get_wanted_rpms_by_key(rpm_unit_keys, import_conduit)
    rpm_unit_keys = None
    copy_rpms(rpms_to_copy, import_conduit)
    rpms_to_copy = None

    names_to_copy = get_wanted_rpms_by_name(rpm_names, import_conduit)
    copy_rpms_by_name(names_to_copy, import_conduit)

    return associated_units


def get_wanted_rpms_by_key(rpm_unit_keys, import_conduit):
    """

    :param rpm_unit_keys:
    :param import_conduit:
    :return: set of namedtuples needed by the dest repo
    """
    named_tuples = set()
    for key in rpm_unit_keys:
        # ignore checksum from updateinfo.xml
        key['checksum'] = None
        key['checksumtype'] = None
        named_tuples.add(models.RPM.NAMEDTUPLE(**key))
    assoc_query_manager = managers.factory.repo_unit_association_query_manager()
    query_func = functools.partial(assoc_query_manager.get_units,
                                   import_conduit.dest_repo_id)
    units = existing.get_existing_units(rpm_unit_keys, models.RPM.UNIT_KEY_NAMES,
                                models.RPM.TYPE, query_func)
    for unit in units:
        for key in unit.keys():
            if key not in models.RPM.UNIT_KEY_NAMES:
                del unit[key]
        # ignore checksum from updateinfo.xml
        unit['checksum'] = None
        unit['checksumtype'] = None
        named_tuples.discard(models.RPM.NAMEDTUPLE(**unit))
    return named_tuples


def get_wanted_rpms_by_name(rpm_names, import_conduit):
    assoc_query_manager = managers.factory.repo_unit_association_query_manager()
    query_func = functools.partial(assoc_query_manager.get_units,
                                   import_conduit.dest_repo_id)
    search_dicts = ({'name': name} for name in rpm_names)
    units = existing.get_existing_units(search_dicts, ['name'],
                                        models.RPM.TYPE, query_func)
    names = set(rpm_names)
    for unit in units:
        names.discard(unit['name'])
    return names


def copy_rpms(unit_tuples, import_conduit):
    available = existing.get_existing_units((_no_checksum_unit_key(unit) for unit in unit_tuples),
                                            models.RPM.UNIT_KEY_NAMES, models.RPM.TYPE,
                                            import_conduit.get_source_units)

    for unit in available:
        import_conduit.associate_unit(unit)


def _no_checksum_unit_key(unit_tuple):
    ret = unit_tuple._asdict()
    # ignore checksum from updateinfo.xml
    del ret['checksum']
    del ret['checksumtype']
    return ret


def copy_rpms_by_name(names, import_conduit):
    to_copy = {}

    search_dicts = ({'name': name} for name in names)
    units = existing.get_existing_units(search_dicts, models.RPM.UNIT_KEY_NAMES,
                                        models.RPM.TYPE,
                                        import_conduit.get_source_units)
    for unit in units:
        model = models.RPM.from_package_info(unit.unit_key)
        previous = to_copy.get(model.key_string_without_version)
        if previous is None:
            to_copy[model.key_string_without_version] = (model.complete_version_serialized, unit)
        else:
            to_copy[model.key_string_without_version] = max(((model.complete_version_serialized, unit), previous))

    for version, unit in to_copy.values():
        import_conduit.associate_unit(unit)


def decide_what_to_get(units):
    groups = set()
    rpm_names = set()
    rpm_unit_keys = []
    for unit in units:
        # TODO: won't work for distribution, but we probably don't care.
        # we should handle that somehow though
        model = models.TYPE_MAP[unit.type_id](metadata=unit.metadata, **unit.unit_key)
        if model.TYPE == models.PackageCategory.TYPE:
            groups.update(model.group_names)
        elif model.TYPE == models.PackageGroup.TYPE:
            rpm_names.update(model.all_package_names)
        elif model.TYPE == models.Errata.TYPE:
            rpm_unit_keys.extend(model.package_unit_keys)
            _LOGGER.info(model.package_unit_keys)
    return groups, rpm_names, rpm_unit_keys


def _associate_unit(dest_repo, import_conduit, unit):
    if unit.type_id in (models.PackageGroup.TYPE, models.PackageCategory.TYPE):
        new_unit = _safe_copy(unit)
        new_unit.unit_key['repo_id'] = dest_repo.id
        saved_unit = import_conduit.save_unit(new_unit)
        return saved_unit
    else:
        import_conduit.associate_unit(unit)
        return unit


def _safe_copy(unit):
    new_unit = copy.deepcopy(unit)
    new_unit.id = None
    for key in new_unit.metadata.keys():
        if key.startswith('_'):
            del new_unit.metadata[key]
    return new_unit
