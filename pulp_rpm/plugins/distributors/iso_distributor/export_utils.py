# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from gettext import gettext as _
import isodate
import json
import os
import re
import shutil

from pulp.common import dateutils
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.exceptions import MissingResource
from pulp.server.managers.repo.distributor import RepoDistributorManager
from pulp.server.managers.repo.query import RepoQueryManager

# import generate_iso from this directory, which is not in the python path
import generate_iso
from pulp_rpm.common import constants, ids, models
from pulp_rpm.yum_plugin import comps_util, updateinfo, metadata
from pulp_rpm.yum_plugin import util as yum_utils

_logger = yum_utils.getLogger(__name__)

ISO_NAME_REGEX = re.compile(r'^[_A-Za-z0-9-]+$')
ASSOCIATED_UNIT_DATE_KEYWORD = 'created'


def is_valid_prefix(file_prefix):
    """
    Used to check if the given file prefix is valid. A valid prefix contains only letters, numbers, _,
    and -

    :param file_prefix: The string used to prefix the export file(s)
    :type  file_prefix: str

    :return: True if the given file_prefix is a valid match; False otherwise
    :rtype:  bool
    """
    return ISO_NAME_REGEX.match(file_prefix) is not None


def cleanup_working_dir(working_dir):
    """
    Removes the given directory tree. If it fails, the exception is logged and not passed on.
    """
    try:
        shutil.rmtree(working_dir)
        _logger.debug('Cleaned up working directory %s' % working_dir)
    except (IOError, OSError), e:
        _logger.exception('unable to clean up working directory; Error: %s' % e)


def form_lookup_key(rpm):
    """
    Takes an an rpm AssociatedUnit.unit_key dict and converts it into a tuple.

    Note: Although pulp considers the checksum type and checksum to be part of the unique key,
    we do not include this here because the errata checksum type does not always match the
    checksum type of the rpm. Calculating the package checksum using the errata checksum type and
    confirming it is the same package would be a nice feature to have.

    Yum appears to assume an epoch of 0 if the epoch does not exist, so that's what we'll do.

    :param rpm:  The rpm unit key to form the lookup key for
    :type  rpm:  dict

    :return: A tuple of the rpm name, epoch, version, release, and arch
    :rtype:  tuple
    """
    rpm_key = (rpm['name'], rpm['epoch'] or '0', rpm['version'], rpm['release'], rpm['arch'])
    return rpm_key


def form_unit_key_map(units):
    """
    Takes a list of rpm units and creates a dict where the key is the result of form_lookup_key

    :param units:   The list of rpm units to convert to a dict
    :type  units:   list of pulp.plugins.model.AssociatedUnit

    :return:        A dict of the units, where the key is is the rpm unit key as a tuple
    :rtype:         dict
    """
    existing_units = {}
    for u in units:
        key = form_lookup_key(u.unit_key)
        existing_units[key] = u
    return existing_units


def validate_export_config(config):
    """
    Currently, the export configuration for a single repository is the same as the group export
    configuration. If this changes, this should be removed, and each distributor should get its
    own custom validation function.

    :param config:  The configuration to validate
    :type  config:  pulp.plugins.config.PluginCallConfiguration

    :return: a tuple in the form (bool, str) where bool is True if the config is valid. The str
            describes the error if the configuration is invalid. i18n is taken into account.
    :rtype:  tuple
    """
    # Check for the required configuration keys, as defined in constants
    for key in constants.EXPORT_REQUIRED_CONFIG_KEYS:
        value = config.get(key)
        if value is None:
            msg = _("Missing required configuration key: %(key)s" % {"key": key})
            _logger.error(msg)
            return False, msg
        if key == constants.PUBLISH_HTTP_KEYWORD:
            config_http = config.get(key)
            if config_http is not None and not isinstance(config_http, bool):
                msg = _("http should be a boolean; got %s instead" % config_http)
                _logger.error(msg)
                return False, msg
        if key == constants.PUBLISH_HTTPS_KEYWORD:
            config_https = config.get(key)
            if config_https is not None and not isinstance(config_https, bool):
                msg = _("https should be a boolean; got %s instead" % config_https)
                _logger.error(msg)
                return False, msg

    # Check for optional and unsupported configuration keys.
    for key in config.keys():
        if key not in constants.EXPORT_REQUIRED_CONFIG_KEYS and \
                key not in constants.EXPORT_OPTIONAL_CONFIG_KEYS:
            msg = _("Configuration key '%(key)s' is not supported" % {"key": key})
            _logger.error(msg)
            return False, msg
        if key == constants.SKIP_KEYWORD:
            metadata_types = config.get(key)
            if metadata_types is not None and not isinstance(metadata_types, list):
                msg = _("skip should be a list; got %s instead" % metadata_types)
                _logger.error(msg)
                return False, msg
        if key == constants.ISO_PREFIX_KEYWORD:
            iso_prefix = config.get(key)
            if iso_prefix is not None and not is_valid_prefix(str(iso_prefix)):
                msg = _("iso_prefix is not valid; valid characters include %s" % ISO_NAME_REGEX.pattern)
                _logger.error(msg)
                return False, msg
        if key == constants.ISO_SIZE_KEYWORD:
            iso_size = config.get(key)
            if iso_size is not None and int(iso_size) < 1:
                msg = _('iso_size is not a positive integer')
                _logger.error(msg)
                return False, msg
        if key == constants.START_DATE_KEYWORD:
            start_date = config.get(key)
            if start_date:
                try:
                    dateutils.parse_iso8601_datetime(str(start_date))
                except isodate.ISO8601Error:
                    msg = _('Start date is not a valid iso8601 datetime. Format: yyyy-mm-ddThh:mm:ssZ')
                    return False, msg
        if key == constants.END_DATE_KEYWORD:
            end_date = config.get(key)
            if end_date:
                try:
                    dateutils.parse_iso8601_datetime(str(end_date))
                except isodate.ISO8601Error:
                    msg = _('End date is not a valid iso8601 datetime. Format: yyyy-mm-ddThh:mm:ssZ')
                    return False, msg
        if key == constants.EXPORT_DIRECTORY_KEYWORD:
            export_dir = config.get(key)
            if export_dir:
                # Check that the export directory exists and is read/writable
                export_dir = str(export_dir)
                if not os.path.isdir(export_dir):
                    msg = _("Value for 'export_dir' is not an existing directory: %s" % export_dir)
                    return False, msg
                if not os.access(export_dir, os.R_OK) or not os.access(export_dir, os.W_OK):
                    msg = _("Unable to read & write to specified 'export_dir': %s" % export_dir)
                    return False, msg

    return True, None


def retrieve_repo_config(repo, config):
    """
    Retrieves the working directory and date filter for a repository. The working directory is the
    export directory if it exists. If it does not, repo.working_dir is used. The relative
    url used during a yum publish for the repo is joined to this.

    :param repo:    The repository to retrieve the configuration for
    :type  repo:    pulp.plugins.model.Repository
    :param config:  the export distributor configuration to use
    :type  config:  pulp.plugins.config.PluginCallConfiguration

    :return: A tuple, (str, dict), consisting of the full path to the working directory and a
            date filter to use directly in a mongo query.
    :rtype:  tuple
    """
    # Retrieve the yum distributor configuration for this repository and extract the relative url
    relative_url = get_repo_relative_url(repo.id)
    # The export directory, if it exists, is where the repo will exported.
    export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)
    # The repository's working directory path
    if export_dir:
        working_dir = os.path.join(str(export_dir), relative_url)
    else:
        working_dir = os.path.join(repo.working_dir, relative_url)
    # Date filter to apply to errata export. If this is none, we export everything.
    date_filter = create_date_range_filter(config)

    return working_dir, date_filter


def retrieve_group_export_config(repo_group, config):
    """
    This processes the config for a repository group. It removes any non-rpm repositories from the list
    of repositories to export, determines the correct working directories for the remaining repositories,
    and retrieves the date filter. The date filter is a dict, which can be used directly in a mongo query

    :param repo_group:  The repository group to get repositories from
    :type  repo_group:  pulp.plugins.model.RepositoryGroup
    :param config:      The configuration to use when creating the date filter and determining the
                        working directory for repositories
    :type  config:      pulp.plugins.config.PluginCallConfiguration

    :return:            Tuple in the following format: (list of (repo_id, working_dir), date_filter).
                        The repo_id and working_dir are of type str, and the date filter is of type
                        dict. working_dir is the full path to the repository's working directory.
    :rtype:             (list of tuple, dict)
    """
    # The export directory, if it exists, is where the group will be exported.
    export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)

    # Create a list of tuples containing rpm repositories and their working directories
    rpm_repositories = []
    for repo_id in repo_group.repo_ids:
        # Since a group might contain non-rpm repositories, filter them out
        if is_rpm_repo(repo_id):
            # Get the relative url used with the yum distributor
            relative_url = get_repo_relative_url(repo_id)
            # If an export directory was given, use that as the working directory, else use the default
            if export_dir:
                working_dir = os.path.join(export_dir, relative_url)
            else:
                working_dir = os.path.join(repo_group.working_dir, relative_url)

            rpm_repositories.append((repo_id, working_dir))
        else:
            _logger.debug('Skipping repo [%s] in group [%s]; not an rpm repo' % (repo_id, repo_group.id))

    date_filter = create_date_range_filter(config)

    return rpm_repositories, date_filter


def get_repo_relative_url(repo_id):
    """
    Retrieve an rpm repository relative url from its distributor configuration.

    :param repo_id: The repo id to get the relative url for
    :type  repo_id: str

    :return: The relative url, or if it could not be retrieved from the distributor config, the
            repository id.
    :rtype:  str
    """
    # Retrieve the yum distributor configuration for this repository and extract the relative url
    try:
        # Try to retrieve the yum distributor config and get the relative url
        yum_config = RepoDistributorManager().get_distributor(repo_id, ids.TYPE_ID_DISTRIBUTOR_YUM)
        relative_url = yum_config['config']['relative_url']
    except (MissingResource, KeyError):
        # If the relative url was not retrieved because it didn't exist, use the repo_id
        relative_url = repo_id

    return relative_url.lstrip('/')


def is_rpm_repo(repo_id):
    """
    Checks if a given repository id is an rpm repository

    :param repo_id: The repository id to check
    :type  repo_id: str

    :return: True if its an rpm repo, false otherwise
    :rtype:  bool
    """
    # Retrieve the the repository configuration from the manager
    try:
        repo_metadata = RepoQueryManager().get_repository(repo_id)
        return repo_metadata['notes']['_repo-type'] == 'rpm-repo'
    except (MissingResource, KeyError):
        return False


def init_progress_report(items_total=0):
    """
    A helper method to create a new progress report dictionary

    :param items_total: Items total in the task. Defaults to 0
    :type  items_total: int

    :return: A progress report
    :rtype:  dict
    """
    return {
        constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING,
        constants.PROGRESS_NUM_SUCCESS_KEY: 0,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: items_total,
        constants.PROGRESS_ITEMS_TOTAL_KEY: items_total,
        constants.PROGRESS_ERROR_DETAILS_KEY: [],
    }


def set_progress(type_id, progress_status, progress_callback):
    """
    This just checks that progress_callback is not None before calling it. The progress callback
    function is called using type_id and progress_status, in that order.

    :param type_id:             The type id to use with the progress callback
    :type  type_id:             str
    :param progress_status:     The progress status to use with the progress callback
    :type  progress_status:     dict
    :param progress_callback:   The progress callback function to use
    :type  progress_callback:   function
    """
    if progress_callback:
        progress_callback(type_id, progress_status)


def create_date_range_filter(config):
    """
    Create a date filter based on start and end issue dates specified in the repo config. The returned
    filter is a dictionary which can be used directly in a mongo query.

    :param config: plugin configuration instance; the proposed repo configuration is found within
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: date filter dict with issued date ranges in mongo query format
    :rtype:  {}
    """
    start_date = config.get(constants.START_DATE_KEYWORD)
    end_date = config.get(constants.END_DATE_KEYWORD)
    date_filter = None
    if start_date and end_date:
        date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$gte": start_date, "$lte": end_date}}
    elif start_date:
        date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$gte": start_date}}
    elif end_date:
        date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$lte": end_date}}
    return date_filter


def export_rpm(working_dir, rpm_units, progress_callback=None):
    """
     This method takes a list of rpm units and exports them to the given working directory

    :param working_dir:         The full path to the directory to export the content to
    :type  working_dir:         str
    :param rpm_units:           the list of rpm units to export
    :type  rpm_units:           list of AssociatedUnit
    :param progress_callback:   callback to report progress info to publish_conduit
    :type  progress_callback:   function

    :return: tuple of status and list of error messages if any occurred
    :rtype:  ({}, [str])
    """
    # get rpm units
    progress_status = init_progress_report(len(rpm_units))

    summary = {
        'num_package_units_attempted': 0,
        'num_package_units_exported': 0,
        'num_package_units_errors': 0,
    }
    details = {'errors': {}}

    errors = []
    for unit in rpm_units:
        set_progress(ids.TYPE_ID_RPM, progress_status, progress_callback)
        source_path = unit.storage_path
        destination_path = os.path.join(working_dir, yum_utils.get_relpath_from_unit(unit))

        if not yum_utils.create_copy(source_path, destination_path):
            msg = "Unable to copy %s to %s" % (source_path, destination_path)
            _logger.error(msg)
            errors.append(msg)
            progress_status[constants.PROGRESS_NUM_ERROR_KEY] += 1
            progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1
            continue
        progress_status[constants.PROGRESS_NUM_SUCCESS_KEY] += 1
        progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1

    summary["num_package_units_attempted"] += len(rpm_units)
    summary["num_package_units_exported"] += len(rpm_units) - len(errors)
    summary["num_package_units_errors"] += len(errors)

    # If errors occurred, write them to details and set the state to failed.
    if errors:
        details['errors']['rpm_export'] = errors
        progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        progress_status[constants.PROGRESS_ERROR_DETAILS_KEY] = errors
        set_progress(models.RPM.TYPE, progress_status, progress_callback)
        return summary, details

    progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
    set_progress(models.RPM.TYPE, progress_status, progress_callback)

    return summary, details


def export_errata(working_dir, errata_units, progress_callback=None):
    """
    This call writes the given errata units to an updateinfo.xml file in the working directory.
    This does not export any packages associated with the errata.

    :param working_dir:         The full path to the directory to export the content to
    :type  working_dir:         str
    :param errata_units:        the errata units to find the rpm units for
    :type  errata_units:        list of pulp.plugins.model.AssociatedUnit
    :param progress_callback:   callback to report progress info to publish_conduit
    :type  progress_callback:   function

    :return: The updateinfo.xml file path
    :rtype:  str
    """
    progress_status = init_progress_report(len(errata_units))

    # If there are no errata units to export, quit.
    if not errata_units:
        progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
        set_progress(ids.TYPE_ID_ERRATA, progress_status, progress_callback)
        return

    # Update the progress status
    progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_RUNNING
    set_progress(ids.TYPE_ID_ERRATA, progress_status, progress_callback)

    # Write the updateinfo.xml file to the working directory
    updateinfo_path = updateinfo.updateinfo(errata_units, working_dir)

    # Set the progress status, summary, and details
    progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
    progress_status[constants.PROGRESS_NUM_SUCCESS_KEY] = len(errata_units)
    progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] = 0
    set_progress(ids.TYPE_ID_ERRATA, progress_status, progress_callback)

    return updateinfo_path


def export_distribution(working_dir, distribution_units, progress_callback=None):
    """
    Export distribution unit involves including files within the unit.
    Distribution is an aggregate unit with distribution files. This call
    looks up each distribution unit and copies the files from the storage location
    to working directory.

    :param working_dir:         The full path to the directory to export the content to
    :type  working_dir:         str
    :param distribution_units:  The distribution units to export. These should be retrieved from the
                                publish conduit using a criteria.
    :type  distribution_units:  list of AssociatedUnit
    :param progress_callback:   callback to report progress info to publish_conduit
    :type  progress_callback:   function

    :return: A tuple of the summary and the details, in that order
    :rtype:  (dict, dict)
    """
    progress_status = init_progress_report()
    set_progress(ids.TYPE_ID_DISTRO, progress_status, progress_callback)
    summary = {}
    details = {'errors': {}}
    _logger.debug('exporting distribution files to %s dir' % working_dir)

    errors = []
    for unit in distribution_units:
        source_path_dir = unit.storage_path
        if 'files' not in unit.metadata:
            msg = "No distribution files found for unit %s" % unit
            _logger.error(msg)
            errors.append(msg)
            continue

        distro_files = unit.metadata['files']
        _logger.debug("Found %s distribution files to symlink" % len(distro_files))
        progress_status[constants.PROGRESS_ITEMS_TOTAL_KEY] = len(distro_files)
        progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] = len(distro_files)
        for dfile in distro_files:
            set_progress(ids.TYPE_ID_DISTRO, progress_status, progress_callback)
            source_path = os.path.join(source_path_dir, dfile['relativepath'])
            destination_path = os.path.join(working_dir, dfile['relativepath'])

            if not yum_utils.create_copy(source_path, destination_path):
                msg = "Unable to copy %s to %s" % (source_path, destination_path)
                _logger.error(msg)
                errors.append(msg)
                progress_status[constants.PROGRESS_NUM_ERROR_KEY] += 1
                progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1
                continue
            progress_status[constants.PROGRESS_NUM_SUCCESS_KEY] += 1
            progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1

    if errors:
        progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED
        progress_status[constants.PROGRESS_ERROR_DETAILS_KEY] = errors
        details['errors']['distribution_errors'] = errors
    else:
        progress_status[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
    summary["num_distribution_units_attempted"] = len(distribution_units)
    summary["num_distribution_units_exported"] = len(distribution_units) - len(errors)
    summary["num_distribution_units_errors"] = len(errors)
    set_progress(ids.TYPE_ID_DISTRO, progress_status, progress_callback)

    return summary, details


def export_package_groups_and_cats(working_dir, units, progress_callback=None):
    """
    Exports the the given package groups and package categories to the given working directory.
    Because both package groups and categories are needed to write the groups xml file, they
    are both exported here.

    :param working_dir:         The full path to the directory to export the content to
    :type  working_dir:         str
    :param units:               The package groups and package categories to export.
    :type  units:               list of AssociatedUnit
    :param progress_callback:   the progress callback function
    :type  progress_callback:   function

    :return: a tuple consisting of the groups_xml_path and the summary, in that order
    :rtype:  (str, dict)
    """
    set_progress(models.PackageGroup.TYPE, {constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING},
                 progress_callback)
    set_progress(models.PackageCategory.TYPE, {constants.PROGRESS_STATE_KEY: constants.STATE_RUNNING},
                 progress_callback)
    summary = {}

    # Collect the existing groups and categories
    existing_groups = filter(lambda u: u.type_id == models.PackageGroup.TYPE, units)
    existing_cats = filter(lambda u: u.type_id == models.PackageCategory.TYPE, units)
    groups_xml_path = comps_util.write_comps_xml(working_dir, existing_groups, existing_cats)
    summary['num_package_groups_exported'] = len(existing_groups)
    summary['num_package_categories_exported'] = len(existing_cats)

    set_progress(models.PackageGroup.TYPE, {constants.PROGRESS_STATE_KEY: constants.STATE_COMPLETE},
                 progress_callback)
    set_progress(models.PackageCategory.TYPE, {constants.PROGRESS_STATE_KEY: constants.STATE_COMPLETE},
                 progress_callback)

    return groups_xml_path, summary


def export_complete_repo(repo_id, working_dir, publish_conduit, config, progress_callback=None):
    """
    Export all content types for a repository, unless the type is in the skip list.

    :param working_dir:         The full path to the directory to export the content to
    :type  working_dir:         str
    :param publish_conduit:     The publish conduit for the repository
    :type  publish_conduit:     pulp.plugins.conduits.repo_publish.RepoPublishConduit
    :param config:              The configuration to use while exporting
    :type  config:              pulp.plugins.config.PluginConfiguration
    :param progress_callback:   The progress callback function to use
    :type  progress_callback:   function

    :return: A tuple containing the summary and the details dictionaries for the export
    :rtype: tuple
    """
    groups_xml = None
    updateinfo_xml = None
    skip_types = config.get(constants.SKIP_KEYWORD) or []
    summary, details = {}, {'errors': {}}

    # Retrieve all the units associated with the repository using the conduit
    errata_criteria = UnitAssociationCriteria(type_ids=[models.Errata.TYPE])
    distro_criteria = UnitAssociationCriteria(type_ids=[models.Distribution.TYPE])
    group_criteria = UnitAssociationCriteria(type_ids=[models.PackageGroup.TYPE,
                                                       models.PackageCategory.TYPE])
    rpm_units = get_rpm_units(publish_conduit)
    errata_units = publish_conduit.get_units(errata_criteria)
    distro_units = publish_conduit.get_units(distro_criteria)
    group_units = publish_conduit.get_units(group_criteria)

    # Export the rpm units
    if models.RPM.TYPE not in skip_types:
        rpm_summary, rpm_details = export_rpm(working_dir, rpm_units, progress_callback)
        summary = dict(summary.items() + rpm_summary.items())
        details = dict(details.items() + rpm_details.items())

    # Export the group units
    if models.PackageGroup.TYPE not in skip_types:
        groups_xml, group_summary = export_package_groups_and_cats(
            working_dir, group_units, progress_callback)
        summary = dict(summary.items() + group_summary.items())

    # Export the distribution units
    if models.Distribution.TYPE not in skip_types:
        export_distribution(working_dir, distro_units, progress_callback)

    # Export the errata
    if models.Errata.TYPE not in skip_types:
        updateinfo_xml = export_errata(working_dir, errata_units, progress_callback)

    # generate metadata with a painfully long call. Note that this method retrieves all the content
    # again to generate the metadata. This could probably be optimized when the yum distributor is
    # rewritten.
    metadata_status, metadata_errors = metadata.generate_yum_metadata(
        repo_id, working_dir, publish_conduit, config, progress_callback, False,
        groups_xml, updateinfo_xml, publish_conduit.get_repo_scratchpad())

    if metadata_errors:
        details['errors']['metadata_errors'] = metadata_errors

    return summary, details


def export_incremental_content(working_dir, publish_conduit, date_filter, progress_callback=None):
    """
    Exports incremental content for a repository. Any rpm or errata unit that was associated
    with the repository in the given date range is copied to the working directories. A JSON document
    containing metadata is also exported for each rpm unit. The errata units are also written as JSON
    documents.

    :param working_dir:         The full path to the directory to export the content to
    :type  working_dir:         str
    :param publish_conduit:     The publish conduit for the repository
    :type  publish_conduit:     pulp.plugins.conduits.repo_publish.RepoPublishConduit
    :param date_filter:         A date filter dict, usually generated by create_date_range_filter
    :type  date_filter:         dict
    :param progress_callback:   callback to report progress info to publish_conduit. This is expected to
                                take the following parameters: a string to use as the key in a
                                dictionary, and the second parameter is assigned to it.
    :type  progress_callback:   function

    :return: A tuple containing the summary and the details dictionaries for the export
    :rtype: tuple
    """
    rpm_units = []
    for model in (models.RPM, models.SRPM, models.DRPM):
        # Here, every field is fetched because we write the errata and rpm metadata to JSON
        criteria = UnitAssociationCriteria(type_ids=[model.TYPE], association_filters=date_filter)
        rpm_units += publish_conduit.get_units(criteria=criteria)

    errata_criteria = UnitAssociationCriteria(type_ids=[models.Errata.TYPE],
                                              association_filters=date_filter)
    errata_units = publish_conduit.get_units(criteria=errata_criteria)

    # Export the rpm units to the working directory
    rpm_summary, rpm_details = export_rpm(working_dir, rpm_units, progress_callback)

    # Export the rpm metadata as JSON files to the working directory
    rpm_json_path = os.path.join(working_dir, 'rpm_json')
    export_rpm_json(rpm_json_path, rpm_units)

    # Export the errata as JSON files to the working directory
    errata_json_path = os.path.join(working_dir, 'errata_json')
    export_errata_json(errata_json_path, errata_units, progress_callback)

    return rpm_summary, rpm_details


def export_rpm_json(working_dir, rpm_units):
    """
    Using the given list of rpm AssociatedUnits, this method writes the rpm metadata to a json file
    in the working directory. The file name is in the format name-version-release.arch.json

    :param working_dir: The full path to the directory to write the json files to
    :type  working_dir: str
    :param rpm_units:   A list of AssociatedUnits of type rpm, drpm, and srpm
    :type  rpm_units:   list of pulp.plugins.model.AssociatedUnit
    """
    if not os.path.isdir(working_dir):
        os.makedirs(working_dir)

    for unit in rpm_units:
        # Create each file name to match the standard rpm file names, but with a json extension
        filename = unit.unit_key['name'] + '-' + unit.unit_key['version'] + '-' + \
            unit.unit_key['release'] + '.' + unit.unit_key['arch'] + '.json'
        path = os.path.join(working_dir, filename)

        # Remove all keys that start with an underscore, like _id and _ns
        for key_to_remove in filter(lambda key: key[0] == '_', unit.metadata.keys()):
            unit.metadata.pop(key_to_remove)
        # repodata will be regenerated on import, so remove it as well
        if 'repodata' in unit.metadata:
            unit.metadata.pop('repodata')

        dict_to_write = {'unit_key': unit.unit_key, 'unit_metadata': unit.metadata}

        with open(path, 'w') as f:
            json.dump(dict_to_write, f)


def export_errata_json(working_dir, errata_units, progress_callback=None):
    """
    Using the given list of errata AssociatedUnits, this method writes the errata to a json file in
    the working directory.

    :param working_dir:         The full path to the directory to write the json files to
    :type  working_dir:         str
    :param errata_units:        A list of AssociatedUnits of type errata
    :type  errata_units:        list of pulp.plugins.model.AssociatedUnit
    :param progress_callback:   callback to report progress info to publish_conduit. This is expected to
                                take the following parameters: a string to use as the key in a
                                dictionary, and the second parameter is assigned to it.
    :type  progress_callback:   function
    """
    progress_report = init_progress_report(len(errata_units))

    if not os.path.isdir(working_dir):
        os.makedirs(working_dir)

    for unit in errata_units:
        # Remove unnecessary keys, like _id
        for key_to_remove in filter(lambda key: key[0] == '_', unit.metadata.keys()):
            unit.metadata.pop(key_to_remove)
        errata_dict = {
            'unit_key': unit.unit_key,
            'unit_metadata': unit.metadata
        }

        json_file_path = os.path.join(working_dir, unit.unit_key['id'] + '.json')
        with open(json_file_path, 'w') as f:
            json.dump(errata_dict, f)

        progress_report[constants.PROGRESS_NUM_SUCCESS_KEY] += 1
        progress_report[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1
        set_progress(models.Errata.TYPE, progress_report, progress_callback)

    progress_report[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
    set_progress(models.Errata.TYPE, progress_report, progress_callback)


def get_rpm_units(publish_conduit, skip_list=()):
    """
    Retrieve a list of rpm units using the publish conduit. By default, this method retrieves
    RPM.TYPE, SRPM.TYPE, and DRPM.TYPE from pulp_rpm.common.models. Use the skip list to
    skip over one or more of these types.

    :param publish_conduit: The publish conduit to retrieve the units from
    :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
    :param skip_list:       A list of type ids to skip. These should be from pulp_rpm.common.models
    :type  skip_list:       tuple

    :return: A list of AssociatedUnits
    :rtype:  list
    """
    rpm_units = []
    for model in (models.RPM, models.SRPM, models.DRPM):
        if model.TYPE not in skip_list:
            # All that is retrieved here is the unit key and its storage path. export_complete_repo
            # relies on metadata.generate_yum_metadata to generate the necessary metadata.
            fields = ['_storage_path']
            fields.extend(model.UNIT_KEY_NAMES)
            criteria = UnitAssociationCriteria(type_ids=model.TYPE, unit_fields=fields)
            rpm_units += publish_conduit.get_units(criteria=criteria)
    return rpm_units


def publish_isos(working_dir, image_prefix, http_dir=None, https_dir=None, image_size=None,
                 progress_callback=None):
    """
    Generate one or more ISO images containing the given working_dir, and then publish them to
    the given http and https directories. Not passing a http or https directory means the ISOs
    won't be published using that method.

    :param working_dir:         The full path to the directory to wrap in ISOs
    :type  working_dir:         str
    :param image_prefix:        The prefix of the image filename
    :type  image_prefix:        str
    :param http_dir:            The full path to the http export directory. The default base path can be
                                found in pulp_rpm.common.constants and should be suffixed by the
                                group or repo id
    :type  http_dir:            str
    :param https_dir:           The full path to the https export directory. The default base path can
                                be found in pulp_rpm.common.constants and should be suffixed by the
                                group or repo id
    :type  https_dir:           str
    :param image_size:          The size of the ISO image in megabytes (defaults to dvd sized iso)
    :type  image_size:          int
    :param progress_callback:   callback to report progress info to publish_conduit. This is expected to
                                take the following parameters: a string to use as the key in a
                                dictionary, and the second parameter is assigned to it.
    :type  progress_callback:   function
    """
    # TODO: Move the ISO output directory
    # Right now the ISOs live in the working directory because there isn't a better place for them.
    # When that changes, the output directory argument should be changed here.
    generate_iso.create_iso(working_dir, working_dir, image_prefix, image_size, progress_callback)

    # Create the directories, if necessary
    if https_dir is not None and not os.path.isdir(https_dir):
        os.makedirs(https_dir)
    if http_dir is not None and not os.path.isdir(http_dir):
        os.makedirs(http_dir)

    # Clean up the working directory, leaving the ISOs. This should change when exported ISOs get
    # a new home.
    for root, dirs, files in os.walk(working_dir):
        for name in dirs:
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)

        # Now link the files to the https and http directories, if they exist
        for name in files:
            if https_dir:
                os.symlink(os.path.join(root, name), os.path.join(https_dir, name))
                set_progress('publish_https', {constants.PROGRESS_STATE_KEY: constants.STATE_COMPLETE},
                             progress_callback)
            else:
                set_progress('publish_https', {constants.PROGRESS_STATE_KEY: constants.STATE_SKIPPED},
                             progress_callback)
            if http_dir:
                os.symlink(os.path.join(root, name), os.path.join(http_dir, name))
                set_progress('publish_http', {constants.PROGRESS_STATE_KEY: constants.STATE_COMPLETE},
                             progress_callback)
            else:
                set_progress('publish_http', {constants.PROGRESS_STATE_KEY: constants.STATE_SKIPPED},
                             progress_callback)
