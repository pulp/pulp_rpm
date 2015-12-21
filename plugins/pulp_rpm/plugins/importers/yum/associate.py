from gettext import gettext as _
import logging

import mongoengine
from pulp.plugins.util.misc import paginate
from pulp.server.controllers import repository as repo_controller

from pulp_rpm.common import constants, ids
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
    :type  source_repo:     pulp.server.db.model.Repository

    :param dest_repo:       destination repo
    :type  dest_repo:       pulp.server.db.model.Repository

    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit

    :param config:          config object for the distributor
    :type  config:          pulp.plugins.config.PluginCallConfiguration

    :param units:           iterable of ContentUnit objects to copy
    :type  units:           iterable

    :return:                List of associated units.
    """
    if units is None:
        # this might use a lot of RAM since RPMs tend to have lots of metadata
        # TODO: so we should probably do something about that
        units = repo_controller.find_repo_content_units(source_repo, yield_content_unit=True)

    # get config items that we care about
    recursive = config.get(constants.CONFIG_RECURSIVE)
    if recursive is None:
        recursive = False

    associated_units = set([_associate_unit(dest_repo, unit) for unit in units])
    # allow garbage collection
    units = None

    associated_units |= copy_rpms(
        (unit for unit in associated_units if isinstance(unit, models.RPM)),
        source_repo, dest_repo, import_conduit, recursive)

    # return here if we shouldn't get child units
    if not recursive:
        return list(associated_units)

    group_ids, rpm_names, rpm_search_dicts = identify_children_to_copy(associated_units)

    # ------ get group children of the categories ------
    for page in paginate(group_ids):
        group_units = models.PackageGroup.objects.filter(repo_id=source_repo.repo_id,
                                                         package_group_id__in=page)
        if group_units.count() > 0:
            associated_units |= set(
                associate(source_repo, dest_repo, import_conduit, config, group_units))

    # ------ get RPM children of errata ------
    wanted_rpms = get_rpms_to_copy_by_key(rpm_search_dicts, import_conduit, source_repo)
    rpm_search_dicts = None
    rpms_to_copy = filter_available_rpms(wanted_rpms, import_conduit, source_repo)
    associated_units |= copy_rpms(rpms_to_copy, source_repo, dest_repo, import_conduit, recursive)
    rpms_to_copy = None

    # ------ get RPM children of groups ------
    names_to_copy = get_rpms_to_copy_by_name(rpm_names, import_conduit, dest_repo)
    associated_units |= copy_rpms_by_name(names_to_copy, source_repo, dest_repo,
                                          import_conduit, recursive)

    return list(associated_units)


def get_rpms_to_copy_by_key(rpm_search_dicts, import_conduit, repo):
    """
    Errata specify NEVRA for the RPMs they reference. This method is useful for
    taking those specifications and finding actual units available in the source
    repository.

    :param rpm_search_dicts:    iterable of dicts that include a subset of rpm
                                unit key parameters
    :type  rpm_search_dicts:    iterable
    :param import_conduit:      import conduit passed to the Importer
    :type  import_conduit:      pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param repo:                repository from which to get RPMs
    :type  repo:                pulp.server.db.model.Repository

    :return: set of namedtuples needed by the dest repo
    :rtype:  set
    """
    # identify which RPMs are desired and store as named tuples
    named_tuples = set()
    for key in rpm_search_dicts:
        # ignore checksum from updateinfo.xml
        key['checksum'] = None
        key['checksumtype'] = None
        named_tuples.add(models.RPM.NAMED_TUPLE(**key))

    # identify which of those RPMs already exist
    existing_units = existing.get_existing_units(rpm_search_dicts, models.RPM, repo)
    # remove units that already exist in the destination from the set of units
    # we want to copy
    for unit in existing_units:
        unit_key = unit.unit_key.copy()
        # ignore checksum from updateinfo.xml
        unit_key['checksum'] = None
        unit_key['checksumtype'] = None
        named_tuples.discard(models.RPM.NAMED_TUPLE(**unit_key))
    return named_tuples


def get_rpms_to_copy_by_name(rpm_names, import_conduit, repo):
    """
    Groups reference names of RPMs. This method is useful for taking those names
    and removing ones that already exist in the destination repository.

    :param rpm_names:       iterable of RPM names
    :type  rpm_names:       iterable
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param repo:            repository from which to get RPMs
    :type  repo:            pulp.server.db.model.Repository

    :return:    set of names that don't already exist in the destination repo
    :rtype:     set
    """
    search_dicts = ({'name': name} for name in rpm_names)
    units = existing.get_existing_units(search_dicts, models.RPM, repo)
    names = set(rpm_names)
    for unit in units:
        names.discard(unit.name)
    return names


def filter_available_rpms(rpms, import_conduit, repo):
    """
    Given a series of RPM named tuples, return an iterable of those which are
    available in the source repository

    :param rpms:            iterable of RPMs that are desired to be copied
    :type  rpms:            iterable of pulp_rpm.plugins.db.models.RPM.NAMEDTUPLE
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param repo:            repository in which to search for RPMs
    :type  repo:            pulp.server.db.model.Repository

    :return:    iterable of Units that should be copied
    :return:    iterable of pulp_rpm.plugins.db.models.RPM
    """
    return existing.get_existing_units((_no_checksum_clean_unit_key(unit) for unit in rpms),
                                       models.RPM, repo)


def copy_rpms(units, source_repo, dest_repo, import_conduit, copy_deps, solver=None):
    """
    Copy RPMs from the source repo to the destination repo, and optionally copy
    dependencies as well. Dependencies are resolved recursively.

    :param units:           iterable of Units
    :type  units:           iterable of pulp_rpm.plugins.db.models.RPM
    :param source_repo: The repository we are copying units from.
    :type source_repo: pulp.server.db.model.Repository
    :param dest_repo: The repository we are copying units to
    :type dest_repo: pulp.server.db.model.Repository
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
        # we are passing in units that may have flattened "provides" metadata.
        # This flattened field is not used by associate_single_unit().
        repo_controller.associate_single_unit(dest_repo, unit)
        unit_set.add(unit)

    if copy_deps and unit_set:
        if solver is None:
            solver = depsolve.Solver(source_repo)

        # This returns units that have a flattened 'provides' metadata field
        # for memory purposes (RHBZ #1185868)
        deps = solver.find_dependent_rpms(unit_set)

        # remove rpms already in the destination repo
        existing_units = set(existing.get_existing_units([dep.unit_key for dep in deps],
                                                         models.RPM, dest_repo))

        # the hash comparison for Units is unit key + type_id, the metadata
        # field is not used.
        to_copy = deps - existing_units

        _LOGGER.debug('Copying deps: %s' % str(sorted([x.name for x in to_copy])))
        if to_copy:
            unit_set |= copy_rpms(to_copy, source_repo, dest_repo, import_conduit, copy_deps,
                                  solver)

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


def copy_rpms_by_name(names, source_repo, dest_repo, import_conduit, copy_deps):
    """
    Copy RPMs from source repo to destination repo by name

    :param names:           iterable of RPM names
    :type  names:           iterable of basestring
    :param source_repo: The repository we are copying units from.
    :type source_repo: pulp.server.db.model.Repository
    :param dest_repo: The repository we are copying units to
    :type dest_repo: pulp.server.db.model.Repository
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit

    :return:    set of pulp.plugins.model.Unit that were copied
    :rtype:     set
    """
    name_q = mongoengine.Q(name__in=names)
    type_q = mongoengine.Q(unit_type_id=ids.TYPE_ID_RPM)
    units = repo_controller.find_repo_content_units(source_repo, units_q=name_q,
                                                    repo_content_unit_q=type_q,
                                                    unit_fields=models.RPM.unit_key_fields,
                                                    yield_content_unit=True)

    return copy_rpms(units, source_repo, dest_repo, import_conduit, copy_deps)


def identify_children_to_copy(units):
    """
    Takes an iterable of Unit instances, and for each that is of a child-bearing
    type (Group, Category, Errata), collects the child definitions.

    :param units:   iterable of Units
    :type  units:   iterable of pulp.server.db.model.ContentUnit

    :return:    set(group names), set(rpm names), list(rpm search dicts)
    """
    groups = set()
    rpm_names = set()
    rpm_search_dicts = []
    for unit in units:
        if isinstance(unit, models.PackageCategory):
            groups.update(unit.packagegroupids)
        elif isinstance(unit, models.PackageGroup):
            rpm_names.update(unit.all_package_names)
        elif isinstance(unit, models.PackageEnvironment):
            groups.update(unit.group_ids)
            groups.update(unit.optional_group_ids)
        elif isinstance(unit, models.Errata):
            rpm_search_dicts.extend(unit.rpm_search_dicts)
    return groups, rpm_names, rpm_search_dicts


def _associate_unit(dest_repo, unit):
    """
    Associate one particular unit with the destination repository. There are
    behavioral exceptions based on type:

    Group, Category, Environment and Yum Metadata File units need to have their "repo_id"
    attribute set.

    RPMs are convenient to do all as one block, for the purpose of dependency
    resolution. So this method skips RPMs and lets them be done together by
    other means

    :param dest_repo:       destination repo
    :type  dest_repo:       pulp.server.db.model.Repository

    :param unit:            Unit to be copied
    :type  unit:            pulp.server.db.model.ContentUnit

    :return:                copied unit
    :rtype:                 pulp.server.db.model.ContentUnit
    """
    if isinstance(unit, (models.PackageGroup, models.PackageCategory, models.PackageEnvironment)):
        return associate_copy_for_repo(unit, dest_repo)
    elif isinstance(unit, models.RPM):
        # copy will happen in one batch
        return unit
    elif isinstance(unit, models.YumMetadataFile):
        return associate_copy_for_repo(unit, dest_repo, True)
    else:
        repo_controller.associate_single_unit(repository=dest_repo, unit=unit)
        return unit


def associate_copy_for_repo(unit, dest_repo, set_content=False):
    """
    Associate a unit where it is required to make a copy of the unit first, and where the unit key
    includes the repo ID.

    :param unit:            Unit to be copied
    :type  unit:            pulp_rpm.plugins.db.models.Package
    :param dest_repo:       destination repo
    :type  dest_repo:       pulp.server.db.model.Repository
    :param set_content:     if True, the set_unit() method will be called on the new unit. Default
                            is False.
    :type  set_content:     bool

    :return:    new unit that was saved and associated
    :rtype:     pulp_rpm.plugins.db.models.Package
    """
    new_unit = unit.clone()
    new_unit.repo_id = dest_repo.repo_id
    if set_content:
        new_unit.set_content(unit._storage_path)

    try:
        new_unit.save()
    except mongoengine.NotUniqueError:
        # It is possible that a previous copy exists as an orphan, in which case it can safely
        # be deleted and replaced with this new version.
        _LOGGER.debug(_('replacing pre-existing copy of %(u)s' % {'u': new_unit}))
        new_unit.__class__.objects.filter(**new_unit.unit_key).delete()
        new_unit.save()

    repo_controller.associate_single_unit(repository=dest_repo, unit=new_unit)
    return new_unit
