import logging
import os

import mongoengine
from pulp.plugins.loader import api as plugin_api
from pulp.plugins.util.misc import paginate
from pulp.server.controllers import repository as repo_controller
from pulp.server.controllers import units as units_controller
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common import ids
from pulp_rpm.plugins.importers.yum.parse import rpm as rpm_parse


_LOGGER = logging.getLogger(__name__)


def check_repo(wanted):
    """
    Given an iterable of units as namedtuples, this function will search for them
    using the given search method and return the set of tuples that were not
    found. This checks for the unit in the db as well as for the actual file
    on the filesystem. Note that the check for the actual file is performed only
    for the supported unit types.

    This is useful in a case where you know what units you want to have in a repo,
    but need to know which you need to actually download by eliminating the ones
    you already have.

    :param wanted:          iterable of units as namedtuples
    :type  wanted:          iterable
    :param sync_conduit:
    :type  sync_conduit:    pulp.plugins.conduits.repo_sync.RepoSyncConduit

    :return:    set of unit keys as namedtuples, identifying which of the
                named tuples received as input were not found by the
                search method.
    :rtype:     set
    """
    # sort by type
    sorted_units = _sort_by_type(wanted)
    # UAQ for each type
    for unit_type, values in sorted_units.iteritems():
        model = plugin_api.get_unit_model_by_id(unit_type)

        fields = model.unit_key_fields + ('_storage_path',)
        rpm_srpm_drpm = unit_type in (ids.TYPE_ID_RPM,
                                      ids.TYPE_ID_SRPM,
                                      ids.TYPE_ID_DRPM)

        # FIXME this function being called doesn't have a fields parameter
        unit_generator = (model(**unit_tuple._asdict()) for unit_tuple in values.copy())
        for unit in units_controller.find_units(unit_generator, fields=fields):
            if rpm_srpm_drpm:
                # For RPMs, SRPMs and DRPMs, also check if the file exists on the filesystem.
                # If not, we do not want to skip downloading the unit.
                if unit._storage_path is None or not os.path.isfile(unit._storage_path):
                    continue
            values.discard(unit.unit_key_as_named_tuple)

    ret = set()
    ret.update(*sorted_units.values())
    return ret


def get_existing_units(search_dicts, unit_class, repo):
    """
    Get units from the given repository that match the search terms. The unit instances will only
    have their unit key fields populated.

    :param search_dicts:    iterable of dictionaries that should be used to search units
    :type  search_dicts:    iterable
    :param unit_class:      subclass representing the type of unit to search for
    :type  unit_class:      pulp_rpm.plugins.db.models.Package
    :param repo:            repository to search in
    :type  repo:            pulp.server.db.model.Repository

    :return:    generator of unit_class instances with only their unit key fields populated
    :rtype:     generator
    """
    unit_fields = unit_class.unit_key_fields
    for segment in paginate(search_dicts):
        unit_filters = {'$or': list(segment)}
        units_q = mongoengine.Q(__raw__=unit_filters)
        association_q = mongoengine.Q(unit_type_id=unit_class._content_type_id.default)

        for result in repo_controller.find_repo_content_units(repo, units_q=units_q,
                                                              repo_content_unit_q=association_q,
                                                              unit_fields=unit_fields,
                                                              yield_content_unit=True):
            yield result


def check_all_and_associate(wanted, conduit, config, download_deferred, catalog):
    """
    Given a set of unit keys as namedtuples, this function checks if a unit
    already exists in Pulp and returns the set of tuples that were not
    found. This checks for the unit in the db as well as for the actual file
    on the filesystem. If a unit exists in the db and the filesystem, this function
    also associates the unit to the given repo. Note that the check for the actual file
    is performed only for the supported unit types.

    :param wanted:            dict where keys are units as namedtuples, and values are
                              WantedUnitInfo instances
    :type  wanted:            dict
    :param conduit:           repo sync conduit
    :type  conduit:           pulp.plugins.conduits.repo_sync.RepoSync
    :param config:            configuration instance passed to the importer
    :type  config:            pulp.plugins.config.PluginCallConfiguration
    :param download_deferred: indicates downloading is deferred (or not).
    :type  download_deferred: bool
    :param catalog:           Deferred downloading catalog.
    :type  catalog:           pulp_rpm.plugins.importers.yum.sync.PackageCatalog

    :return:    set of unit keys as namedtuples, identifying which of the
                named tuples received as input were not found on the server.
    :rtype:     set
    """
    sorted_units = _sort_by_type(wanted.iterkeys())
    for unit_type, values in sorted_units.iteritems():
        model = plugin_api.get_unit_model_by_id(unit_type)
        # FIXME "fields" does not get used, but it should
        # fields = model.unit_key_fields + ('_storage_path',)
        unit_generator = (model(**unit_tuple._asdict()) for unit_tuple in values.copy())
        for unit in units_controller.find_units(unit_generator):
            is_rpm_drpm_srpm = unit_type in (ids.TYPE_ID_RPM, ids.TYPE_ID_SRPM, ids.TYPE_ID_DRPM)
            file_exists = unit._storage_path is not None and os.path.isfile(unit._storage_path)
            if is_rpm_drpm_srpm:
                # no matter what is the download policy, if existing unit has a valid storage_path,
                # we need to set the downloaded flag to True
                if file_exists and not unit.downloaded:
                    unit.downloaded = True
                    unit.save()
                # Existing RPMs, DRPMs and SRPMs are disqualified when the associated
                # package file does not exist and downloading is not deferred.
                if not download_deferred and not file_exists:
                    continue
            catalog.add(unit, wanted[unit.unit_key_as_named_tuple].download_path)
            if rpm_parse.signature_enabled(config):
                try:
                    rpm_parse.filter_signature(unit, config)
                except PulpCodedException as e:
                    _LOGGER.debug(e)
                    continue
            repo_controller.associate_single_unit(conduit.repo, unit)
            values.discard(unit.unit_key_as_named_tuple)
    still_wanted = set()
    still_wanted.update(*sorted_units.values())
    return still_wanted


def _sort_by_type(wanted):
    ret = {}
    for unit in wanted:
        ret.setdefault(unit.__class__.__name__, set()).add(unit)
    return ret
