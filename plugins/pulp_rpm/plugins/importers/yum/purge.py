from gettext import gettext as _
import functools
import logging

from pulp.common.plugins import importer_constants
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.managers.repo.unit_association import RepoUnitAssociationManager
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
    for model in (models.RPM, models.SRPM, models.DRPM):
        units = {}
        for unit in get_existing_units(model, conduit.get_units):
            model_instance = model(metadata=unit.metadata, **unit.unit_key)
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
        named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
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
    :rtype:     iterable of pulp.plugins.model.Unit
    """
    criteria = UnitAssociationCriteria([model.TYPE],
                                       unit_fields=model.UNIT_KEY_NAMES)
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

        for model in package_info_generator:
            named_tuple = model.as_named_tuple
            remote_named_tuples.add(named_tuple)

    finally:
        file_handle.close()
    return remote_named_tuples


def remove_unit_duplicate_nevra(unit_key, type_id, repo_id):
    """
    Removes units from the repo that have same NEVRA, ignoring the checksum
    and checksum type.

    :param unit_key: dictionary of key:value pairs that make a unique
                     identifier of the unit specified by the user
    :type unit_key: dict
    :param type_id: type of unit being checked for duplicate nevra
    :type type_id:  str
    :param repo_id: id of the repo from which units will be unassociated
    :type repo_id:  str
    """
    nevra_filters = unit_key.copy()
    del nevra_filters['checksum']
    del nevra_filters['checksumtype']
    list_filters = []
    for i in nevra_filters.items():
        list_filters.append(dict([i]))
    filters = {'$and': list_filters}
    criteria = UnitAssociationCriteria(type_ids=type_id, unit_filters=filters)
    # unassociate unit from repo that match given criteria
    RepoUnitAssociationManager.unassociate_by_criteria(repo_id, criteria)
