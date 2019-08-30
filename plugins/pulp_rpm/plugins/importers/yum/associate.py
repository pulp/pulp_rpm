from gettext import gettext as _
import logging

import mongoengine
import os
from pulp.plugins.util.misc import paginate
from pulp.server.controllers import repository as repo_controller
from pulp.server.db import model as platform_models
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import pulp_solv
from pulp_rpm.plugins.importers.yum import existing
from pulp_rpm.plugins.importers.yum.parse import rpm as rpm_parse


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

    :param units:           generator of ContentUnit objects to copy
    :type  units:           generator

    :return:                List of associated units.
    """
    if units is None:
        # this might use a lot of RAM since RPMs tend to have lots of metadata
        # TODO: so we should probably do something about that
        units = repo_controller.find_repo_content_units(source_repo, yield_content_unit=True)

    # get config items that we care about
    recursive = config.get(constants.CONFIG_RECURSIVE) or \
        config.get(constants.CONFIG_RECURSIVE_CONSERVATIVE)
    additional_repos = config.get(constants.CONFIG_ADDITIONAL_REPOS, {})
    if additional_repos and not recursive:
        # TODO: is there a better error to raise?
        raise ValueError("Cannot use additional_repos without one of the recursive flags set")

    repo_map = additional_repos
    repo_map[source_repo.repo_id] = dest_repo.repo_id

    if recursive:
        solver = pulp_solv.Solver(
            source_repo,
            target_repo=dest_repo,
            conservative=config.get(constants.CONFIG_RECURSIVE_CONSERVATIVE),
            additional_repos=additional_repos,
            ignore_missing=False
            # the line above disables the code which injects "dummy solvables" to provide
            # missing packages. it is not known whether that code is 100% necessary, but it
            # is feeding invalid data to libsolv somehow resulting in a violated invariant
            # and failure on an assert statement here
            # https://github.com/openSUSE/libsolv/blob/master/src/solver.c#L1979-L1981
        )
        # Only loads the original source and destination repositories
        solver.load()

    # make a collection from generator to be able to iterate through it several times
    units = set(units)

    if not recursive:
        # shallow dependency resolution - ensure we copy copy module artifacts

        # directly associate everything that is not an RPM ahead of time
        # we need to filter out rpm units since in reality they were not associated
        associated_units = set([
            _associate_unit(dest_repo, unit, config)
            for unit in units if not isinstance(unit, models.RPM)
        ])
        if None in associated_units:
            _LOGGER.warning(_('%s packages failed signature filter and were not imported.'
                              % len(associated_units)))
        associated_units |= copy_rpms(
            [unit for unit in units if unit._content_type_id == ids.TYPE_ID_RPM],
            source_repo, dest_repo, import_conduit, config
        )

        # always copy module artifacts
        # this copies the artifacts but not the modules. should this be copying modules too?
        (group_ids, rpm_names, rpm_search_dicts,
         module_search_dicts) = identify_children_to_copy(associated_units,
                                                          parent_type=models.Modulemd)
        wanted_rpms = get_rpms_to_copy_by_key(rpm_search_dicts, import_conduit, source_repo)
        del rpm_search_dicts
        rpms_to_copy = filter_available_rpms(wanted_rpms, import_conduit, source_repo)
        associated_units |= copy_rpms(rpms_to_copy, source_repo, dest_repo, import_conduit, config)
        del rpms_to_copy

        failed_units = set(units) - associated_units

        # garbage collection
        del units

        return associated_units, failed_units

    (group_ids, rpm_names, rpm_search_dicts,
        module_search_dicts) = identify_children_to_copy(units)

    # ------ get group children of the categories ------
    while True:
        added = False

        for page in paginate(group_ids):
            group_units = models.PackageGroup.objects.filter(repo_id=source_repo.repo_id,
                                                             package_group_id__in=page)
            if group_units.count() > 0:
                units |= set(group_units)
                added = True

        (group_ids, rpm_names, rpm_search_dicts,
            module_search_dicts) = identify_children_to_copy(units)

        if not added:
            break

    # ------ get RPM children of errata and modules ------
    wanted_rpms = get_rpms_to_copy_by_key(rpm_search_dicts, import_conduit, source_repo)
    rpm_search_dicts = None
    rpms_to_copy = filter_available_rpms(wanted_rpms, import_conduit, source_repo)
    units |= set(rpms_to_copy)
    del rpms_to_copy

    # ------ get Module children of Errata ------
    source_repo_modules = set(existing.get_existing_units(
        module_search_dicts, models.Modulemd, source_repo))
    dest_repo_modules = set(existing.get_existing_units(
        module_search_dicts, models.Modulemd, dest_repo))

    units |= source_repo_modules - dest_repo_modules
    del module_search_dicts
    del source_repo_modules
    del dest_repo_modules

    # ------ get RPM children of groups ------
    rpms_to_copy = get_rpms_to_copy_by_name(rpm_names, import_conduit, dest_repo)
    units |= set(rpms_to_copy)
    del rpms_to_copy

    # default dict where key=repo_id and value=set of units to copy
    units_by_repo = resolve_dependent_units(units, solver, source_repo.repo_id)

    associated_units = set()
    failed_units = set()

    for src_repo_id, units_to_copy in units_by_repo.items():
        src_repo = platform_models.Repository.objects.get(
            repo_id=src_repo_id)
        dst_repo = platform_models.Repository.objects.get(
            repo_id=repo_map[src_repo_id])
        # directly associate everything that is not an RPM ahead of time
        # we need to filter out rpm units since in reality they were not associated
        associated_units |= set([
            _associate_unit(dst_repo, unit, config)
            for unit in units_to_copy if not isinstance(unit, models.RPM)
        ])
        if None in associated_units:
            _LOGGER.warning(_('%s packages failed signature filter and were not imported.'
                              % len(associated_units)))
        associated_units |= copy_rpms(
            [unit for unit in units_to_copy if unit._content_type_id == ids.TYPE_ID_RPM],
            src_repo, dst_repo, import_conduit, config
        )
        failed_units |= units_to_copy - associated_units

        # Update content unit counts
        # This is normally done by core for the destination repository, however, that will
        # not update things for our additional repositories, so we have to do it ourself
        if associated_units and dst_repo.repo_id != dest_repo.repo_id:
            repo_controller.update_last_unit_added(dst_repo.repo_id)
            repo_controller.rebuild_content_unit_counts(dst_repo)

    # filter out these types from the set of failed units because they must be cloned, not
    # simply copied, and the cloned units are not identical to the originals and thus
    # get erroneously included in the set of failed units.
    # this is not a good "solution" but a "good solution" is not forthcoming. this has also
    # been a longstanding issue that went totally unnoticed for a long time.
    failed_units = set([
        unit for unit in failed_units if not
        isinstance(unit, (models.YumMetadataFile, models.ModulemdDefaults))
    ])

    # allow garbage collection
    del units

    return associated_units, failed_units


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

    name_q = mongoengine.Q(name__in=names)
    type_q = mongoengine.Q(unit_type_id=ids.TYPE_ID_RPM)
    units = repo_controller.find_repo_content_units(repo, units_q=name_q,
                                                    repo_content_unit_q=type_q,
                                                    unit_fields=models.RPM.unit_key_fields,
                                                    yield_content_unit=True)
    return units


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


def resolve_dependent_units(units, solver, source_repo_id):
    """
    Given a set of units, use a provided libsolv solver to resolve dependencies.

    All of the incoming units are presumed to be from the source repo with
    the provided ID. Because Libsolv only knows about RPMs, Modules, and
    Module Defaults, we have to strip out all other types of units and then
    add them back to the set of units to be copied from the source_repo.

    :param units:  iterable of Units
    :type units:   iterable of content models
    :param solver:  if not None, it is used to resolve dependencies as specified in
                    "Requires" lines in the RPM metadata.
    :type solver:   pulp_solv.Solver
    :param source_repo_id: The repo ID of the units provided in 'units'
    :type source_repo_id:  str

    :return:      set of pulp.plugins.models.Unit that were copied
    :rtype:       set
    """
    depsolvable_types = set([ids.TYPE_ID_RPM, ids.TYPE_ID_MODULEMD, ids.TYPE_ID_MODULEMD_DEFAULTS])
    unit_set = set(unit for unit in units if unit._content_type_id in depsolvable_types)

    deps = solver.find_dependent_rpms(unit_set)
    # this function is meant to be called only once using a set of source units all from one
    # repository (i.e. units matching the criteria and their children)
    # some of those units are of a type not in depsolvable_types so we must add them back to the
    # set to ensure they get copied
    deps[source_repo_id] |= units
    return deps


def copy_rpms(units, source_repo, dest_repo, import_conduit, config):
    """
    Copy RPMs (and modules) from the source repo to the destination repo.

    :param units:           iterable of Units
    :type  units:           iterable of pulp_rpm.plugins.db.models.RPM
    :param source_repo: The repository we are copying units from.
    :type source_repo: pulp.server.db.model.Repository
    :param dest_repo: The repository we are copying units to
    :type dest_repo: pulp.server.db.model.Repository
    :param import_conduit:  import conduit passed to the Importer
    :type  import_conduit:  pulp.plugins.conduits.unit_import.ImportUnitConduit
    :param config:          configuration instance passed to the importer of the destination repo
    :type  config:          pulp.plugins.config.PluginCallConfiguration

    :return:    set of pulp.plugins.models.Unit that were copied
    :rtype:     set
    """
    if not isinstance(units, set):
        unit_set = set(units)
    else:
        unit_set = units

    failed_signature_check = 0
    for unit in unit_set.copy():
        assert unit._content_type_id == ids.TYPE_ID_RPM
        # we are passing in units that may have flattened "provides" metadata.
        # This flattened field is not used by associate_single_unit().
        if rpm_parse.signature_enabled(config):
            if unit.downloaded:
                try:
                    rpm_parse.filter_signature(unit, config)
                except PulpCodedException as e:
                    _LOGGER.debug(e)
                    failed_signature_check += 1
                    unit_set.remove(unit)
                    continue
            else:
                continue
        _LOGGER.debug('Copying unit: %s', unit)
        # TODO(performance): this should be done in bulks
        repo_controller.associate_single_unit(dest_repo, unit)

    if failed_signature_check:
        _LOGGER.warning(_('%s packages failed signature filter and were not imported.'
                        % failed_signature_check))
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


def identify_children_to_copy(units, parent_type=None):
    """
    Takes an iterable of Unit instances, and for each that is of a child-bearing
    type (Group, Category, Errata, Modulemd), collects the child definitions.

    :param units:   iterable of Units
    :type  units:   iterable of pulp.server.db.model.ContentUnit
    :param parent_type: unit type for which children should be identified.
                        If None, all types are processed.
    :type  parent_type: pulp.server.db.model.ContentUnit

    :return:    set(group names), set(rpm names), list(rpm search dicts), list(module search dicts)
    """
    groups = set()
    rpm_names = set()
    rpm_search_dicts = []
    module_search_dicts = []
    for unit in units:
        if isinstance(unit, models.PackageCategory) and \
                (parent_type is None or parent_type is models.PackageCategory):
            groups.update(unit.packagegroupids)
        elif isinstance(unit, models.PackageGroup) and \
                (parent_type is None or parent_type is models.PackageGroup):
            rpm_names.update(unit.all_package_names)
        elif isinstance(unit, models.PackageEnvironment) and \
                (parent_type is None or parent_type is models.PackageEnvironment):
            groups.update(unit.group_ids)
            groups.update(unit.optional_group_ids)
        elif isinstance(unit, models.Errata) and \
                (parent_type is None or parent_type is models.Errata):
            # Errata can refer to both RPM and Modulemd units
            rpm_search_dicts.extend(unit.rpm_search_dicts)
            module_search_dicts.extend(unit.module_search_dicts)
        elif isinstance(unit, models.Modulemd) and \
                (parent_type is None or parent_type is models.Modulemd):
            rpm_search_dicts.extend(unit.rpm_search_dicts)
    return groups, rpm_names, rpm_search_dicts, module_search_dicts


def _associate_unit(dest_repo, unit, config):
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

    :param config:          configuration instance passed to the importer of the destination repo
    :type  config:          pulp.plugins.config.PluginCallConfiguration

    :return:                copied unit or None if the unit was not copied
    :rtype:                 pulp.server.db.model.ContentUnit
    """
    types_to_be_copied = (
        models.PackageGroup,
        models.PackageCategory,
        models.PackageEnvironment,
        models.PackageLangpacks
    )
    if isinstance(unit, types_to_be_copied):
        return associate_copy_for_repo(unit, dest_repo)
    elif isinstance(unit, models.RPM):
        # copy will happen in one batch
        return unit
    elif isinstance(unit, (models.YumMetadataFile, models.ModulemdDefaults)):
        return associate_copy_for_repo(unit, dest_repo, True)
    elif isinstance(unit, (models.DRPM, models.SRPM)):
            if rpm_parse.signature_enabled(config):
                if unit.downloaded:
                    try:
                        rpm_parse.filter_signature(unit, config)
                    except PulpCodedException as e:
                        _LOGGER.debug(e)
                        return
            repo_controller.associate_single_unit(repository=dest_repo, unit=unit)
            return unit
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
    :param set_content:     if True, the set_storage_path() method will be called on the new unit.
                            Default is False.
    :type  set_content:     bool

    :return:    new unit that was saved and associated
    :rtype:     pulp_rpm.plugins.db.models.Package
    """
    new_unit = unit.clone()
    new_unit.repo_id = dest_repo.repo_id
    if set_content:
        # calculate a new storage path since the unit key has changed
        new_unit.set_storage_path(os.path.basename(unit._storage_path))

    try:
        new_unit.save()
    except mongoengine.NotUniqueError:
        # It is possible that a previous copy exists as an orphan, in which case it can safely
        # be deleted and replaced with this new version.
        _LOGGER.debug(_('replacing pre-existing copy of %(u)s' % {'u': new_unit}))
        existing_unit_qs = new_unit.__class__.objects.filter(**new_unit.unit_key)
        repo_controller.disassociate_units(dest_repo, existing_unit_qs)
        existing_unit_qs.delete()
        new_unit.save()

    if set_content:
        new_unit.safe_import_content(unit._storage_path)

    repo_controller.associate_single_unit(repository=dest_repo, unit=new_unit)
    return new_unit
