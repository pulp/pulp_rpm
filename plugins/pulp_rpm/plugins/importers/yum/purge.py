import functools
import logging
import operator
from gettext import gettext as _
from itertools import repeat

from mongoengine import Q
from pulp.common.plugins import importer_constants
from pulp.server.db import model
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.controllers import repository as repo_controller
from pymongo.errors import OperationFailure

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import packages, primary, presto, updateinfo, group


_logger = logging.getLogger(__name__)


def purge_unwanted_units(metadata_files, conduit, config):
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
    """
    if config.get_boolean(importer_constants.KEY_UNITS_REMOVE_MISSING) is True:
        _logger.info(_('Removing missing units.'))
        remove_missing_rpms(metadata_files, conduit)
        remove_missing_drpms(metadata_files, conduit)
        remove_missing_errata(metadata_files, conduit)
        remove_missing_groups(metadata_files, conduit)
        remove_missing_categories(metadata_files, conduit)
        remove_missing_environments(metadata_files, conduit)

    retain_old_count = config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
    if retain_old_count is not None:
        _logger.info(_('Removing old units.'))
        num_to_keep = int(retain_old_count) + 1
        remove_old_versions(num_to_keep, conduit)


def remove_old_versions(num_to_keep, conduit):
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
                conduit.remove_unit(versions.pop(oldest_version))


def remove_missing_rpms(metadata_files, conduit):
    """
    Remove RPMs from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    """
    file_function = functools.partial(metadata_files.get_metadata_file_handle,
                                      primary.METADATA_FILE_NAME)
    remote_named_tuples = get_remote_units(file_function, primary.PACKAGE_TAG,
                                           primary.process_package_element)
    remove_missing_units(conduit, models.RPM, remote_named_tuples)


def remove_missing_drpms(metadata_files, conduit):
    """
    Remove DRPMs from the local repository which do not exist in the remote
    repository.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    """
    remote_named_tuples = set()
    for metadata_file_name in presto.METADATA_FILE_NAMES:
        file_function = functools.partial(metadata_files.get_metadata_file_handle,
                                          metadata_file_name)
        file_tuples = get_remote_units(file_function, presto.PACKAGE_TAG,
                                       presto.process_package_element)
        remote_named_tuples = remote_named_tuples.union(file_tuples)

    remove_missing_units(conduit, models.DRPM, remote_named_tuples)


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
                                           updateinfo.process_package_element)
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
    process_func = functools.partial(group.process_group_element, conduit.repo_id)
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
    process_func = functools.partial(group.process_category_element, conduit.repo_id)
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
    process_func = functools.partial(group.process_environment_element, conduit.repo_id)
    remote_named_tuples = get_remote_units(file_function, group.ENVIRONMENT_TAG, process_func)
    remove_missing_units(conduit, models.PackageEnvironment, remote_named_tuples)


def remove_missing_units(conduit, model, remote_named_tuples):
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
    """
    for unit in get_existing_units(model, conduit.get_units):
        named_tuple = model(**unit.unit_key).unit_key_as_named_tuple
        try:
            # if we found it, remove it so we can free memory as we go along
            remote_named_tuples.remove(named_tuple)
        except KeyError:
            conduit.remove_unit(unit)


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
    Q_type_filter = Q(unit_type_id=unit._content_type_id)
    unit_iterator = repo_controller.find_repo_content_units(repo,
                                                            repo_content_unit_q=Q_type_filter,
                                                            units_q=Q_nevra_filter,
                                                            yield_content_unit=True)
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
        for unit_ids in _duplicate_key_id_generator(unit_type):
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


def _duplicate_key_id_generator(unit):
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
        return _duplicate_key_id_generator_aggregation(unit, fields)
    except OperationFailure:
        # mongodb doesn't support aggregation cursors, use the slower mapreduce method
        _logger.info('Purging duplicate NEVRA can take significantly longer in versions of '
                     'mongodb lower than 2.6. Consider upgrading mongodb if cleaning duplicate '
                     'packages takes an unreasonably long time.')
        return _duplicate_key_id_generator_mapreduce(unit, fields)


def _duplicate_key_id_generator_aggregation(unit, fields):
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

    # create the aggregation params by zipping the fields with 1
    # It is a happy coincidence that the two dicts are the same values
    pipeline_opts = dict(zip(fields, repeat(1)))

    # for $sort, this indicates ascending sort for nevra fields
    sort = {'$sort': pipeline_opts}

    # for $project, this indicates what fields to include in the result
    project = {'$project': pipeline_opts}

    # When aggregating over hundreds of thousands of packages, mongo can overflow
    # To prevent this, mongo needs to be allowed to temporarily use the disk for this transaction
    aggregation = unit.objects.aggregate(sort, project, allowDiskUse=True)

    # loop state tracking vars
    previous_nevra = None
    previous_pkg_id = None
    yielding_ids = None

    for pkg in aggregation:
        # strip the checksums and mongo metadata so they don't get used in equality checks
        current_nevra = tuple(pkg[field] for field in fields)
        # current nevra matches previous: this is a duplicate nevra
        if current_nevra == previous_nevra:
            if yielding_ids is None:
                # The current nevra is a duplicate but yielding_ids is None, which means
                # this iteration is the first to detect a duplicate for this nevra.
                # Initialize the list of ids to yield with the *previous* id,
                # since it was the first unit seen with the current nevra
                yielding_ids = [previous_pkg_id]

            # After yielding_ids is initialized with the first unit,
            # append the current package id for each duplicate nevra seen
            yielding_ids.append(pkg['_id'])

        # current nevra doesn't match previous: this is a new nevra
        else:
            # if the duplicate detection populated yielding_ids, yield it now
            # and reset yielding ids for the next potential duplicate
            if yielding_ids:
                yield yielding_ids
                yielding_ids = None

        # stash the current state for comparison in the next iteration
        previous_nevra = current_nevra
        previous_pkg_id = pkg['_id']

    # after the pkg loop, if the last pkg was a duplicate, the yielding else clause won't run
    # in that case, do one final yield to make sure all potential duplicates are yielded
    if yielding_ids:
        yield yielding_ids


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
