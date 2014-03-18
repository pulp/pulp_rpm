import copy
import logging
import os
import shutil

from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import constants
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import depsolve
from pulp_rpm.plugins.importers.yum import existing


_LOGGER = logging.getLogger(__name__)


def associate(source_repo, dest_repo, import_conduit, config, units=None):
    """
    This is the primary method to call when a copy operation is desired. This
    gets called directly by the Importer

    Certain variables are set to "None" as the method progresses so that they
    may be garbage collected.

    :param source_repo:     source repo
    :type  source_repo:     pulp.plugins.model.Repository
    :param dest_repo:       destination repo
    :type  dest_repo:       pulp.plugins.model.Repository
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param config:          config object for the distributor
    :type  config:          pulp.plugins.config.PluginCallConfiguration
    :param units:           iterable of Unit objects to copy
    :type  units:           iterable
    :return:
    """
    if units is None:
        # this might use a lot of RAM since RPMs tend to have lots of metadata
        # TODO: so we should probably do something about that
        units = import_conduit.get_source_units()

    # get config items that we care about
    recursive = config.get(constants.CONFIG_RECURSIVE)
    if recursive is None:
        recursive = False

    associated_units = set([_associate_unit(dest_repo, import_conduit, unit) for unit in units])
    # allow garbage collection
    units = None

    associated_units |= copy_rpms((unit for unit in associated_units if unit.type_id == models.RPM.TYPE),
              import_conduit, recursive)

    # return here if we shouldn't get child units
    if not recursive:
        return list(associated_units)

    group_ids, rpm_names, rpm_search_dicts = identify_children_to_copy(associated_units)

    # ------ get group children of the categories ------
    group_criteria = UnitAssociationCriteria([models.PackageGroup.TYPE],
                                             unit_filters={'id': {'$in': list(group_ids)}})
    group_units = list(import_conduit.get_source_units(group_criteria))
    if group_units:
        associated_units |= set(associate(source_repo, dest_repo, import_conduit, config, group_units))

    # ------ get RPM children of errata ------
    wanted_rpms = get_rpms_to_copy_by_key(rpm_search_dicts, import_conduit)
    rpm_search_dicts = None
    rpms_to_copy = filter_available_rpms(wanted_rpms, import_conduit)
    associated_units |= copy_rpms(rpms_to_copy, import_conduit, recursive)
    rpms_to_copy = None

    # ------ get RPM children of groups ------
    names_to_copy = get_rpms_to_copy_by_name(rpm_names, import_conduit)
    associated_units |= copy_rpms_by_name(names_to_copy, import_conduit, recursive)

    return list(associated_units)


def get_rpms_to_copy_by_key(rpm_search_dicts, import_conduit):
    """
    Errata specify NEVRA for the RPMs they reference. This method is useful for
    taking those specifications and finding actual units available in the source
    repository.

    :param rpm_search_dicts:    iterable of dicts that include a subset of rpm
                                unit key parameters
    :type  rpm_search_dicts:    iterable
    :param import_conduit:      import conduit passed to the Importer
    :type  import_conduit:      pulp.plugins.conduits.unit_import.ImportUnitConduit

    :return: set of namedtuples needed by the dest repo
    """
    # identify which RPMs are desired and store as named tuples
    named_tuples = set()
    for key in rpm_search_dicts:
        # ignore checksum from updateinfo.xml
        key['checksum'] = None
        key['checksumtype'] = None
        named_tuples.add(models.RPM.NAMEDTUPLE(**key))

    # identify which of those RPMs already exist
    existing_units = existing.get_existing_units(rpm_search_dicts, models.RPM.UNIT_KEY_NAMES,
                                models.RPM.TYPE, import_conduit.get_destination_units)
    # remove units that already exist in the destination from the set of units
    # we want to copy
    for unit in existing_units:
        unit_key = unit.unit_key.copy()
        # ignore checksum from updateinfo.xml
        unit_key['checksum'] = None
        unit_key['checksumtype'] = None
        named_tuples.discard(models.RPM.NAMEDTUPLE(**unit_key))
    return named_tuples


def get_rpms_to_copy_by_name(rpm_names, import_conduit):
    """
    Groups reference names of RPMs. This method is useful for taking those names
    and removing ones that already exist in the destination repository.

    :param rpm_names:       iterable of RPM names
    :type  rpm_names:       iterable
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit

    :return:    set of names that don't already exist in the destination repo
    :rtype:     set
    """
    search_dicts = ({'name': name} for name in rpm_names)
    units = existing.get_existing_units(search_dicts, models.RPM.UNIT_KEY_NAMES,
                                        models.RPM.TYPE, import_conduit.get_destination_units)
    names = set(rpm_names)
    for unit in units:
        names.discard(unit.unit_key['name'])
    return names


def filter_available_rpms(rpms, import_conduit):
    """
    Given a series of RPM named tuples, return an iterable of those which are
    available in the source repository

    :param rpms:            iterable of RPMs that are desired to be copied
    :type  rpms:            iterable of pulp_rpm.plugins.db.models.RPM.NAMEDTUPLE
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :return:    iterable of Units that should be copied
    :return:    iterable of pulp.plugins.model.Unit
    """
    return existing.get_existing_units((_no_checksum_clean_unit_key(unit) for unit in rpms),
                                        models.RPM.UNIT_KEY_NAMES, models.RPM.TYPE,
                                        import_conduit.get_source_units)


def copy_rpms(units, import_conduit, copy_deps, solver=None):
    """
    Copy RPMs from the source repo to the destination repo, and optionally copy
    dependencies as well. Dependencies are resolved recursively.

    :param units:           iterable of Units
    :type  units:           iterable of pulp.plugins.models.Unit
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param copy_deps:       if True, copies dependencies as specified in "Requires"
                            lines in the RPM metadata. Matches against NEVRAs
                            and Provides declarations that are found in the
                            source repository. Silently skips any dependencies
                            that cannot be resolved within the source repo.
    :param solver:          an object that can be used for dependency solving.
                            this is useful so that data can be cached in the
                            depsolving object and re-used by each iteration of
                            this method.
    :type  solver:          pulp_rpm.plugins.importers.yum.depsolve.Solver

    :return:    set of pulp.plugins.models.Unit that were copied
    :rtype:     set
    """
    unit_set = set()

    for unit in units:
        import_conduit.associate_unit(unit)
        unit_set.add(unit)

    if copy_deps and unit_set:
        if solver is None:
            solver = depsolve.Solver(import_conduit.get_source_units)
        deps = solver.find_dependent_rpms(unit_set)
        # remove rpms already in the destination repo
        existing_units = set(existing.get_existing_units([dep.unit_key for dep in deps],
                                                         models.RPM.UNIT_KEY_NAMES, models.RPM.TYPE,
                                                         import_conduit.get_destination_units))
        to_copy = deps - existing_units
        _LOGGER.debug('Copying deps: %s' % str(sorted([x.unit_key['name'] for x in to_copy])))
        if to_copy:
            unit_set |= copy_rpms(to_copy, import_conduit, copy_deps, solver)

    return unit_set


def _no_checksum_clean_unit_key(unit_tuple):
    """
    Return a unit key that does not include the checksum or checksumtype. This
    is useful when resolving dependencies, because those unit specifications
    (on "Requires" lines in spec files) do not specify particular checksum info.

    This also removes any key-value pairs where the value is None, which is
    particularly useful for repos where the errata to not specify epochs

    :param unit_tuple:  unit to convert
    :type  unit_tuple:  pulp_rpm.plugins.db.models.RPM.NAMEDTUPLE

    :return:    unit key without checksum data
    :rtype:     dict
    """
    ret = unit_tuple._asdict()
    # ignore checksum from updateinfo.xml
    del ret['checksum']
    del ret['checksumtype']
    for key, value in ret.items():
        if value is None:
            del ret[key]
    return ret


def copy_rpms_by_name(names, import_conduit, copy_deps):
    """
    Copy RPMs from source repo to destination repo by name

    :param names:           iterable of RPM names
    :type  names:           iterable of basestring
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit

    :return:    set of pulp.plugins.model.Unit that were copied
    :rtype:     set
    """
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

    return copy_rpms((unit for v, unit in to_copy.itervalues()), import_conduit, copy_deps)


def identify_children_to_copy(units):
    """
    Takes an iterable of Unit instances, and for each that is of a child-bearing
    type (Group, Category, Errata), collects the child definitions.

    :param units:   iterable of Units
    :type  units:   iterable of pulp.plugins.models.Unit

    :return:    set(group names), set(rpm names), list(rpm search dicts)
    """
    groups = set()
    rpm_names = set()
    rpm_search_dicts = []
    for unit in units:
        # TODO: won't work for distribution, but we probably don't care.
        # we should handle that somehow though
        model = models.TYPE_MAP[unit.type_id](metadata=unit.metadata, **unit.unit_key)
        if model.TYPE == models.PackageCategory.TYPE:
            groups.update(model.group_names)
        elif model.TYPE == models.PackageGroup.TYPE:
            rpm_names.update(model.all_package_names)
        elif model.TYPE == models.PackageEnvironment.TYPE:
            groups.update(model.group_ids)
            groups.update(model.optional_group_ids)
        elif model.TYPE == models.Errata.TYPE:
            rpm_search_dicts.extend(model.rpm_search_dicts)
    return groups, rpm_names, rpm_search_dicts


def _associate_unit(dest_repo, import_conduit, unit):
    """
    Associate one particular unit with the destination repository. There are
    behavioral exceptions based on type:

    Group, Category, Environment and Yum Metadata File units need to have their "repo_id"
    attribute set.

    RPMs are convenient to do all as one block, for the purpose of dependency
    resolution. So this method skips RPMs and lets them be done together by
    other means

    :param dest_repo:       destination repo
    :type  dest_repo:       pulp.plugins.model.Repository
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param unit:            Unit to be copied
    :type  unit:            pulp.plugins.model.Unit

    :return:                copied unit
    :rtype:                 pulp.plugins.model.Unit
    """
    if unit.type_id in (models.PackageGroup.TYPE,
                        models.PackageCategory.TYPE,
                        models.PackageEnvironment.TYPE):
        new_unit = _safe_copy_unit_without_file(unit)
        new_unit.unit_key['repo_id'] = dest_repo.id
        saved_unit = import_conduit.save_unit(new_unit)
        return saved_unit
    elif unit.type_id == models.RPM.TYPE:
        # copy will happen in one batch
        return unit
    elif unit.type_id == models.YumMetadataFile.TYPE:
        model = models.YumMetadataFile(unit.unit_key['data_type'], dest_repo.id, unit.metadata)
        model.clean_metadata()
        relative_path = os.path.join(model.relative_dir, os.path.basename(unit.storage_path))
        new_unit = import_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, relative_path)
        shutil.copyfile(unit.storage_path, new_unit.storage_path)
        import_conduit.save_unit(new_unit)
        return new_unit
    else:
        import_conduit.associate_unit(unit)
        return unit


def _safe_copy_unit_without_file(unit):
    """
    Makes a deep copy of the unit, removes its "id", and removes anything in
    "metadata" whose key starts with a "_".

    :param unit:    unit to be copied
    :type  unit:    pulp.plugins.model.Unit

    :return:        copy of the unit
    :rtype unit:    pulp.plugins.model.Unit
    """
    new_unit = copy.deepcopy(unit)
    new_unit.id = None
    for key in new_unit.metadata.keys():
        if key.startswith('_'):
            del new_unit.metadata[key]
    return new_unit
