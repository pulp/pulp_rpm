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

from pulp.common.plugins import importer_constants
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.managers.repo.unit_association import OWNER_TYPE_IMPORTER

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd import packages, primary, presto, updateinfo, group


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
        remove_missing_rpms(metadata_files, conduit)
        remove_missing_drpms(metadata_files, conduit)
        remove_missing_errata(metadata_files, conduit)
        remove_missing_groups(metadata_files, conduit)
        remove_missing_categories(metadata_files, conduit)

    retain_old_count = config.get(importer_constants.KEY_UNITS_RETAIN_OLD_COUNT)
    if retain_old_count is not None:
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
    remote_named_tuples = get_remote_units(metadata_files, primary.METADATA_FILE_NAME,
                                            primary.PACKAGE_TAG, primary.process_package_element)
    remove_missing_units(metadata_files, conduit, models.RPM, remote_named_tuples)


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
    remote_named_tuples = get_remote_units(metadata_files, presto.METADATA_FILE_NAME,
                                            presto.PACKAGE_TAG, presto.process_package_element)
    remove_missing_units(metadata_files, conduit, models.DRPM, remote_named_tuples)


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
    remote_named_tuples = get_remote_units(metadata_files, updateinfo.METADATA_FILE_NAME,
                                           updateinfo.PACKAGE_TAG, updateinfo.process_package_element)
    remove_missing_units(metadata_files, conduit, models.Errata, remote_named_tuples)


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
    remote_named_tuples = get_remote_units(metadata_files, group.METADATA_FILE_NAME,
                                           group.GROUP_TAG, group.process_group_element)
    remove_missing_units(metadata_files, conduit, models.PackageGroup, remote_named_tuples)


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
    remote_named_tuples = get_remote_units(metadata_files, group.METADATA_FILE_NAME,
                                           group.CATEGORY_TAG, group.process_category_element)
    remove_missing_units(metadata_files, conduit, models.PackageCategory, remote_named_tuples)


def remove_missing_units(metadata_files, conduit, model, remote_named_tuples):
    """
    Generic method to remove units that are in the local repository but missing
    from the upstream repository. This consults the metadata and compares it with
    the contents of the local repo, removing units as appropriate.

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param conduit:         a conduit from the platform containing the get_units
                            and remove_unit methods.
    :type  conduit:         pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param model:           subclass of pulp_rpm.common.models.Package
    :type  model:           pulp_rpm.common.models.Package
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

    :param model:               subclass of pulp_rpm.common.models.Package
    :type  model:               pulp_rpm.common.models.Package
    :param unit_search_func:    function that takes one parameter, a
                                UnitAssociationCriteria, and searches for units
                                in the relevant repository.
    :type  unit_search_func;    function

    :return:    iterable of Unit instances that appear in the repository
    :rtype:     iterable of pulp.plugins.model.Unit
    """
    assoc_filters = {'owner_type': OWNER_TYPE_IMPORTER}
    criteria = UnitAssociationCriteria([model.TYPE],
                                       unit_fields=model.UNIT_KEY_NAMES,
                                       association_filters=assoc_filters)
    return unit_search_func(criteria)


def get_remote_units(metadata_files, file_name, tag, process_func):
    """
    return a set of units (as named tuples) that are in the remote repository

    :param metadata_files:  object containing metadata files from the repo
    :type  metadata_files:  pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param file_name:       name of the metadata file to access. This is not a
                            path on disk, but the name used in the main "repomd.xml"
                            file such as "primary", "comps", etc.
    :type  file_name:       basestring
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
