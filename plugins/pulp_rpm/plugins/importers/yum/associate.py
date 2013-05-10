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
from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import depsolve
from pulp_rpm.plugins.importers.yum import existing

_LOGGER = logging.getLogger(__name__)


def associate(source_repo, dest_repo, import_conduit, config, units=None):
    if units is None:
        # this might use a lot of RAM since RPMs tend to have lots of metadata
        # TODO: so we should probably do something about that
        units = import_conduit.get_source_units()

    associated_units = [_associate_unit(dest_repo, import_conduit, unit) for unit in units]
    units = None

    copy_rpms((unit for unit in associated_units if unit.type_id == models.RPM.TYPE), import_conduit, True)

    # TODO: return here if we shouldn't get child units

    group_ids, rpm_names, rpm_unit_keys = identify_children_to_copy(associated_units)

    # ------ get group children of the categories ------
    group_criteria = UnitAssociationCriteria([models.PackageGroup.TYPE],
                                             unit_filters={'id': {'$in': list(group_ids)}})
    group_units = list(import_conduit.get_source_units(group_criteria))
    if group_units:
        associate(source_repo, dest_repo, import_conduit, config, group_units)

    # ------ get RPM children of errata ------
    wanted_rpms = get_wanted_rpms_by_key(rpm_unit_keys, import_conduit)
    rpm_unit_keys = None
    rpms_to_copy = filter_available_rpms(wanted_rpms, import_conduit)
    copy_rpms(rpms_to_copy, import_conduit)
    rpms_to_copy = None

    # ------ get RPM children of groups ------
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


def filter_available_rpms(rpms, conduit):
    return existing.get_existing_units((_no_checksum_unit_key(unit) for unit in rpms),
                                        models.RPM.UNIT_KEY_NAMES, models.RPM.TYPE,
                                        conduit.get_source_units)


def filter_existing_rpms(rpms, conduit):
    return set(rpms) - set(existing.check_repo(rpms, conduit.get_destination_units))


def copy_rpms(units, import_conduit, copy_deps=False):
    if copy_deps:
        units = set(units)

    for unit in units:
        import_conduit.associate_unit(unit)

    if copy_deps:
        deps = depsolve.find_dependent_rpms(units, import_conduit.get_source_units)
        # only consider deps that exist in the source repo
        available_deps = set(filter_available_rpms(deps, import_conduit))
        # remove rpms already in the destination repo
        existing_units = set(existing.get_existing_units([dep.unit_key for dep in available_deps], models.RPM.UNIT_KEY_NAMES, models.RPM.TYPE, import_conduit.get_destination_units))
        to_copy = available_deps - existing_units
        _LOGGER.debug('Copying deps: %s' % str(sorted([x.unit_key['name'] for x in to_copy])))
        if to_copy:
            copy_rpms(to_copy, import_conduit, copy_deps)


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

    copy_rpms((unit for v, unit in to_copy.itervalues()), import_conduit)


def identify_children_to_copy(units):
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
    return groups, rpm_names, rpm_unit_keys


def _associate_unit(dest_repo, import_conduit, unit):
    if unit.type_id in (models.PackageGroup.TYPE, models.PackageCategory.TYPE):
        new_unit = _safe_copy(unit)
        new_unit.unit_key['repo_id'] = dest_repo.id
        saved_unit = import_conduit.save_unit(new_unit)
        return saved_unit
    elif unit.type_id == models.RPM.TYPE:
        # copy will happen in one batch
        return unit
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
