import functools
import logging
import operator
from gettext import gettext as _
from itertools import repeat
from collections import defaultdict

from mongoengine import Q
from pulp.plugins.loader import api as plugin_api
from pulp.common.plugins import importer_constants
from pulp.server.db import model
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.controllers import repository as repo_controller
from pymongo.errors import OperationFailure

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import packages, primary, presto, updateinfo, group


_logger = logging.getLogger(__name__)


def purge_unwanted_units(metadata_files, conduit, config, catalog):
    """
    START HERE - this is probably the method you want to call in this module

    Remove units from the local repository based on:

    - whether a "retain-old-count" has been set in the config
    - whether "remove-missing" has been set in the config

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param config:          config object for this plugin
    :type  config:          pulp.plugins.config.PluginCallConfiguration
    :param catalog:         The deferred downloading catalog.
    :type catalog:          pulp_rpm.plugins.importers.yum.sync.PackageCatalog
    """
    if config.get_boolean(importer_constants.KEY_UNITS_REMOVE_MISSING) is True:
        _logger.info(_('Removing missing units.'))
        remove_missing_rpms(metadata_files, conduit, catalog)
        remove_missing_drpms(metadata_files, conduit, catalog)
        remove_missing_errata(metadata_files, conduit)
        remove_missing_groups(metadata_files, conduit)
        remove_missing_categories(metadata_files, conduit)
        remove_missing_environments(metadata_files, conduit)

    retain_old_count = config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
    if retain_old_count is not None:
        _logger.info(_('Removing old units.'))
        num_to_keep = int(retain_old_count) + 1
        remove_old_versions(num_to_keep, conduit, catalog)


def remove_old_versions(num_to_keep, conduit, catalog):
    """
    For RPMs, and then separately DRPMs, this loads the unit key of each unit
    in the repo and organizes them by the non-version unique identifiers. For
    each, it removes old versions as necessary to stay within the number of
    versions we want to keep.

    :param num_to_keep: For each package, how many versions should be kept
    :type  num_to_keep: int
    :param conduit:     a conduit from the platform containing the get_units
                        and remove_unit methods.
    :type  conduit:     pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param catalog:         The deferred downloading catalog.
    :type catalog:          pulp_rpm.plugins.importers.yum.sync.PackageCatalog
    """
    for unit_type in (models.RPM, models.SRPM, models.DRPM):
        units = {}
        for unit in get_existing_units(unit_type, conduit.get_units):
            model_instance = unit_type(**unit.unit_key)
            key = model_instance.key_string_without_version
            serialized_version = model_instance.complete_version_serialized
            versions = units.setdefault(key, {})
            versions[serialized_version] = unit

            # if we are over the limit, evict the oldest
            if len(versions) > num_to_keep:
                oldest_version = min(versions)
                unwanted_unit = versions.pop(oldest_version)
                conduit.remove_unit(unwanted_unit)
                catalog.delete(unwanted_unit)


def remove_missing_rpms(metadata_files, conduit, catalog):
    """
    Remove RPMs from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param catalog:         The deferred downloading catalog.
    :type catalog:          pulp_rpm.plugins.importers.yum.sync.PackageCatalog
    """
    file_function = functools.partial(metadata_files.get_metadata_file_handle,
                                      primary.METADATA_FILE_NAME)
    remote_named_tuples = get_remote_units(file_function, primary.PACKAGE_TAG,
                                           primary.process_package_element_nevra_only)
    remove_missing_units(conduit, models.RPM, remote_named_tuples, catalog)
    remove_missing_units(conduit, models.SRPM, remote_named_tuples, catalog)


def remove_missing_drpms(metadata_files, conduit, catalog):
    """
    Remove DRPMs from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param catalog:         The deferred downloading catalog.
    :type catalog:          pulp_rpm.plugins.importers.yum.sync.PackageCatalog
    """
    remote_named_tuples = set()
    for metadata_file_name in presto.METADATA_FILE_NAMES:
        file_function = functools.partial(metadata_files.get_metadata_file_handle,
                                          metadata_file_name)
        file_tuples = get_remote_units(file_function, presto.PACKAGE_TAG,
                                       presto.process_package_element)
        remote_named_tuples = remote_named_tuples.union(file_tuples)

    remove_missing_units(conduit, models.DRPM, remote_named_tuples, catalog)


def remove_missing_errata(metadata_files, conduit):
    """
    Remove Errata from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    """
    file_function = functools.partial(metadata_files.get_metadata_file_handle,
                                      updateinfo.METADATA_FILE_NAME)
    remote_named_tuples = get_remote_units(file_function, updateinfo.PACKAGE_TAG,
                                           updateinfo.process_package_element_errata_id_only)
    remove_missing_units(conduit, models.Errata, remote_named_tuples)


def remove_missing_groups(metadata_files, conduit):
    """
    Remove Groups from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    """
    file_function = metadata_files.get_group_file_handle
    process_func = functools.partial(group.process_group_element_id_only, conduit.repo_id)
    remote_named_tuples = get_remote_units(file_function, group.GROUP_TAG, process_func)
    remove_missing_units(conduit, models.PackageGroup, remote_named_tuples)


def remove_missing_categories(metadata_files, conduit):
    """
    Remove Categories from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    """
    file_function = metadata_files.get_group_file_handle
    process_func = functools.partial(group.process_category_element_id_only, conduit.repo_id)
    remote_named_tuples = get_remote_units(file_function, group.CATEGORY_TAG, process_func)
    remove_missing_units(conduit, models.PackageCategory, remote_named_tuples)


def remove_missing_environments(metadata_files, conduit):
    """
    Remove Categories from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    """
    file_function = metadata_files.get_group_file_handle
    process_func = functools.partial(group.process_environment_element_id_only, conduit.repo_id)
    remote_named_tuples = get_remote_units(file_function, group.ENVIRONMENT_TAG, process_func)
    remove_missing_units(conduit, models.PackageEnvironment, remote_named_tuples)


def remove_missing_units(conduit, model, remote_named_tuples, catalog=None):
    """
    Generic method to remove units that are in the local repository but missing
    from the upstream repository. This consults the metadata and compares it with
    the contents of the local repo, removing units as appropriate.

    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param model:           subclass of pulp_rpm.plugins.db.models.Package
    :type  model:           pulp_rpm.plugins.db.models.Package
    :param remote_named_tuples: set of named tuples representing units in the
                                remote repository
    :type  remote_named_tuples: set
    :param catalog:         The deferred downloading catalog.
    :type catalog:          pulp_rpm.plugins.importers.yum.sync.PackageCatalog
    """
    for unit in get_existing_units(model, conduit.get_units):
        named_tuple = model(**unit.unit_key).unit_key_as_named_tuple
        try:
            # if we found it, remove it so we can free memory as we go along
            remote_named_tuples.remove(named_tuple)
        except KeyError:
            conduit.remove_unit(unit)
            if catalog:
                catalog.delete(unit)


def get_existing_units(model, unit_search_func):
    """
    Get an iterable of Units that are already in the local repository

    :param model:               subclass of pulp_rpm.plugins.db.models.Package
    :type  model:               pulp_rpm.plugins.db.models.Package
    :param unit_search_func:    function that takes one parameter, a
                                UnitAssociationCriteria, and searches for units
                                in the relevant repository.
    :type  unit_search_func;    function

    :return:    iterable of Unit instances that appear in the repository
    :rtype:     iterable of pulp.server.db.model.ContentUnit
    """
    criteria = UnitAssociationCriteria([model._content_type_id.default],
                                       unit_fields=model.unit_key_fields)
    return unit_search_func(criteria)


def get_remote_units(file_function, tag, process_func):
    """
    return a set of units (as named tuples) that are in the remote repository

    :param file_function:   Method that returns a file handle for the units file on disk.
    :type  file_function:   function
    :param tag:             name of the XML tag that identifies each object
                            in the XML file
    :type  tag:             basestring
    :param process_func:    function that takes one argument, of type
                            xml.etree.ElementTree.Element, or the cElementTree
                            equivalent, and returns a dictionary containing
                            metadata about the unit
    :type  process_func:    function

    :return:    set of named tuples representing units
    :rtype:     set
    """
    remote_named_tuples = set()
    file_handle = file_function()

    if file_handle is None:
        return set()
    try:
        package_info_generator = packages.package_list_generator(file_handle,
                                                                 tag,
                                                                 process_func)
        for unit in package_info_generator:
            named_tuple = unit.unit_key_as_named_tuple
            remote_named_tuples.add(named_tuple)

    finally:
        file_handle.close()
    return remote_named_tuples


def remove_unit_duplicate_nevra(unit, repo):
    """
    Removes units from the repo that have same NEVRA, ignoring the checksum
    and checksum type.

    :param unit: The unit whose NEVRA should be removed
    :type unit: ContentUnit
    :param repo: the repo from which units will be unassociated
    :type repo: pulp.server.db.model.Repository
    """
    nevra_filters = unit.unit_key.copy()
    del nevra_filters['checksum']
    del nevra_filters['checksumtype']
    Q_filters = [Q(**{key: value}) for key, value in nevra_filters.iteritems()]
    Q_nevra_filter = reduce(operator.and_, Q_filters)

    _model = plugin_api.get_unit_model_by_id(unit.type_id)
    unit_iterator = _model.objects(q_obj=Q_nevra_filter)

    repo_controller.disassociate_units(repo, unit_iterator)


def remove_repo_duplicate_nevra(repo_id):
    """
    Removes duplicate units that have same NEVRA from a repo, keeping only the most recent unit

    This function is for bulk operations on an entire repo, such as after syncing a repo.
    When operating on single units, consider using :py:func:`remove_unit_duplicate_nevra` instead.

    :param repo_id: ID of the repo from which units with duplicate nevra will be unassociated
    :type repo_id: str
    """
    for unit_type in (models.RPM, models.SRPM, models.DRPM):
        for unit_ids in _duplicate_key_id_generator(unit_type, repo_id):
            # q objects don't deal with order_by, so they can't be used with repo_controller funcs
            # disassociate_units only uses the unit_id, so limit the resultset to only that field
            rcus = model.RepositoryContentUnit.objects.filter(
                repo_id=repo_id, unit_id__in=unit_ids).order_by('-updated').only('unit_id')

            # 0 or 1 packages from the duplicate nevra search match this repo means no duplicates
            if rcus.count() < 2:
                continue

            repo = model.Repository.objects.get(repo_id=repo_id)

            # Since the repo_units queryset is ordered by the updated field (descending), the
            # first repo content unit is the latest. All other RCUs should be disassociated
            duplicate_units = (unit_type(id=rcu.unit_id) for rcu in rcus[1:])
            repo_controller.disassociate_units(repo, duplicate_units)


def _duplicate_key_nevra_fields(unit):
    """strip out fields not related to nevra from a nevra-supporting unit key

    :param unit: unit with NEVRA fields to be filtered
    :type unit: ContentUnit
    """
    # consider duplicates to be units with the same unit key when the checksum is ignored.
    # normally that means NEVRA, but with DRPMs, for example, filename is used instead of name
    fields = list(unit.NAMED_TUPLE._fields)
    fields.remove('checksum')
    fields.remove('checksumtype')
    return fields


def _duplicate_key_id_generator(unit, repo_id):
    """duplicate NEVRA unit ID generator

    :param unit: The unit whose NEVRA should be removed
    :type unit: ContentUnit

    find all duplicate NEVRAs, regardless of repository, for a given content unit type

    This is a memory-efficient pre-filter, which finds all possible duplicate NEVRAs in the
    collection of a content unit that supports the NEVRA fields. This iterator can then be
    cross-referenced with a repository to remove duplicate repository content unit
    links for a given NEVRA.
    """
    fields = _duplicate_key_nevra_fields(unit)

    try:
        # this test aggregation is needed because the aggregation generator body
        # won't raise OperationFailure until its first iteration, at which point it's too late to
        # switch to the mapreduce generator. this also ensures that if OperationFailure is raised
        # at this point, it's specifically because an unsupported aggregation feature was requested
        unit.objects.aggregate({'$limit': 1})
        return _duplicate_key_id_generator_aggregation(unit, fields, repo_id)
    except OperationFailure:
        # mongodb doesn't support aggregation cursors, use the slower mapreduce method
        _logger.info('Purging duplicate NEVRA can take significantly longer in versions of '
                     'mongodb lower than 2.6. Consider upgrading mongodb if cleaning duplicate '
                     'packages takes an unreasonably long time.')
        return _duplicate_key_id_generator_mapreduce(unit, fields)


def _duplicate_key_id_generator_aggregation(unit, fields, repo_id):
    """Superior Aggregation version of duplicate nevra unit ID generator for mongo 2.6+

    In order to find potential duplicate nevras, a mongo aggregation pipeline is employed
    to sort a unit's entire collection based on non-checksum unit key fields. Doing the sorting
    purely as a normal QuerySet overflow's mongo's sort stage bugger, and doing it purely with
    python uses too much memory. Running things through the aggregation pipelines results in
    an iterable that makes it relatively simple to spit out potential duplicate unit IDs without
    breaking either mongo or python. Because the resulting dataset can be rather large, it is
    important to be able to use a mongo db cursor to iterate over the results, which is sadly
    unsupported in 2.4. In that case, the mapreduce method below must be used.

    :param unit: The unit whose NEVRA should be removed
    :type unit: ContentUnit
    :param fields: list of fields that define a given unit type's NEVRA fields
    :type fields: list
    """

    foreign_col = 'units'
    foreign_fields = ['.'.join([foreign_col, '_id'])]
    for field in fields:
        foreign_fields.append('.'.join([foreign_col, field]))

    # create the aggregation params by zipping the fields with 1
    # It is a happy coincidence that the two dicts are the same values
    pipeline_opts = dict(zip(foreign_fields, repeat(1)))

    lookup = {'$lookup': {'from': unit._meta['collection'],
                          'localField': 'unit_id', 'foreignField': '_id', 'as': foreign_col}}

    match = {'$match': {'repo_id': repo_id, 'unit_type_id': unit._content_type_id.default}}

    unwind = {'$unwind': '$' + foreign_col}

    # for $project, this indicates what fields to include in the result
    project = {'$project': pipeline_opts}

    # When aggregating over hundreds of thousands of packages, mongo can overflow
    # To prevent this, mongo needs to be allowed to temporarily use the disk for this transaction
    # It should be ok to set the batch size to 100 as it is not doing sorting. The results should
    # be returned within 100ms to a few seconds (if the IO is really slow).
    # Simply reduce the batchSize if you are getting the cursor timeout. According to my tests,
    # the getMore query is performed slower when setting low batchSize like 5.
    aggregation = model.RepositoryContentUnit.objects.aggregate(lookup, match, unwind, project,
                                                                allowDiskUse=True,
                                                                batchSize=100)

    package_group = defaultdict(list)
    duplicates = set()
    for data in aggregation:
        pkg = data[foreign_col]
        # Just in case pkg is empty but I think it is unlikly to happen
        if not pkg:
            continue

        # strip the checksums and mongo metadata so they don't get used in equality checks
        nevra = tuple(pkg[field] for field in fields)
        package_group[nevra].append(pkg['_id'])
        if len(package_group[nevra]) > 1:
            duplicates.add(nevra)

    for nevra in duplicates:
        yield package_group[nevra]


def _duplicate_key_id_generator_mapreduce(unit, fields):
    """Inferior MapReduce version of duplicate nevra unit ID generator for mongo 2.4

    In order to find potential duplicate nevras, a mongo mapReduce is employed to sift units
    with duplicate nevra in a unit's entire collection based on non-checksum unit key fields.
    This produces the same results as the aggregation mechanism above, but is far slower. Its
    one redeemind quality, relatively speaking, is that it works in mongo 2.4.

    :param unit: The unit whose NEVRA should be removed
    :type unit: ContentUnit
    :param fields: list of fields that define a given unit type's NEVRA fields
    :type fields: list
    """

    if unit is models.DRPM:
        name_field = 'filename'
    else:
        name_field = 'name'

    # going with % interpolation here because all the {}'s make .format no fun for JS...
    # map all units in the collect into key value pairs, where the key is the unit
    # key fields joined by '-', and the value is the unit id
    map_f = """
    function () {
        var key_fields = [this.%s, this.epoch, this.version, this.release, this.arch]
        emit(key_fields.join('-'), {ids: [this._id]});
    }
    """ % name_field

    # reduce keys with multiple values down by collecting ids into a single return object
    reduce_f = """
    function (key, values) {
      // collect mapped values into the first value to build the list of ids for this key/nevra
      var collector = values[0]
      // since collector is values[0] start this loop at index 1
      // reduce isn't called if map only emits one result for key,
      // so there is at least one value to collect
      for (var i = 1; i < values.length; i++) {
        collector.ids = collector.ids.concat(values[i].ids)
      }
      return collector
    }
    """

    # to save time and memory, only return id lists with multiple values, undefing the singles
    finalize_f = """
    function (key, reduced) {
        if (reduced.ids.length > 1) {
            return reduced;
        }
        // if there's only one value after reduction, this key is useless
        // undefined is implicitly returned here, which saves space
    }
    """

    reduced_units = unit.objects.map_reduce(map_f, reduce_f, 'inline', finalize_f)
    for reduced in reduced_units:
        # filter out the undefined (now None) values created in the finalize step
        if reduced.value:
            yield reduced.value['ids']
