import logging
import os

from pulp.plugins.util.misc import paginate
from pulp.server.db.model.criteria import Criteria, UnitAssociationCriteria

from pulp_rpm.plugins.db import models
from pulp_rpm.yum_plugin.util import get_relpath_from_unit


_LOGGER = logging.getLogger(__name__)


def check_repo(wanted, unit_search_method):
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
        model = models.TYPE_MAP[unit_type]
        fields = model.UNIT_KEY_NAMES + ('_storage_path',)
        rpm_srpm_drpm = unit_type in (models.RPM.TYPE, models.SRPM.TYPE, models.DRPM.TYPE)
        unit_keys_generator = (unit._asdict() for unit in values.copy())

        for unit in get_existing_units(unit_keys_generator, fields, unit_type, unit_search_method):
            if rpm_srpm_drpm:
                # For RPMs, SRPMs and DRPMs, also check if the file exists on the filesystem.
                # If not, we do not want to skip downloading the unit.
                if unit.storage_path is None or not os.path.isfile(unit.storage_path):
                    continue
            named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
            values.discard(named_tuple)

    ret = set()
    ret.update(*sorted_units.values())
    return ret


def get_existing_units(search_dicts, unit_fields, unit_type, search_method):
    """

    :param search_dicts:
    :param unit_fields:
    :param unit_type:
    :param search_method:
    :return:    generator of Units
    """
    for segment in paginate(search_dicts):
        unit_filters = {'$or': list(segment)}
        criteria = UnitAssociationCriteria([unit_type], unit_filters=unit_filters,
                                           unit_fields=unit_fields, association_fields=[])
        for result in search_method(criteria):
            yield result


def check_all_and_associate(wanted, sync_conduit):
    """
    Given a set of unit keys as namedtuples, this function checks if a unit
    already exists in Pulp and returns the set of tuples that were not
    found. This checks for the unit in the db as well as for the actual file
    on the filesystem. If a unit exists in the db and the filesystem, this function
    also associates the unit to the given repo. Note that the check for the actual file
    is performed only for the supported unit types.

    :param wanted:          iterable of units as namedtuples
    :type  wanted:          iterable
    :param sync_conduit:    repo sync conduit
    :type  sync_conduit:    pulp.plugins.conduits.repo_sync.RepoSync

    :return:    set of unit keys as namedtuples, identifying which of the
                named tuples received as input were not found on the server.
    :rtype:     set
    """
    sorted_units = _sort_by_type(wanted)
    for unit_type, values in sorted_units.iteritems():
        model = models.TYPE_MAP[unit_type]
        unit_fields = model.UNIT_KEY_NAMES + ('_storage_path', 'filename')
        rpm_srpm_drpm = unit_type in (models.RPM.TYPE, models.SRPM.TYPE, models.DRPM.TYPE)
        rpm_or_srpm = unit_type in (models.RPM.TYPE, models.SRPM.TYPE)

        unit_keys_generator = (unit._asdict() for unit in values.copy())
        for unit in get_all_existing_units(unit_keys_generator, unit_fields, unit_type,
                                           sync_conduit.search_all_units):
            # For RPMs, SRPMs and DRPMs, also check if the file exists on the filesystem.
            # If not, we do not want to skip downloading the unit.
            if rpm_srpm_drpm:
                if unit.storage_path is None or not os.path.isfile(unit.storage_path):
                    continue

            # Since the unit is already downloaded, call respective sync_conduit calls to import
            # the unit in given repository.
            if rpm_or_srpm:
                unit_key = unit.unit_key
                rpm_or_srpm_unit = model(unit_key['name'], unit_key['epoch'], unit_key['version'],
                                         unit_key['release'], unit_key['arch'],
                                         unit_key['checksumtype'], unit_key['checksum'],
                                         unit.metadata)
                relative_path = rpm_or_srpm_unit.relative_path
            else:
                relative_path = get_relpath_from_unit(unit)
            downloaded_unit = sync_conduit.init_unit(unit_type, unit.unit_key,
                                                     unit.metadata, relative_path)
            sync_conduit.save_unit(downloaded_unit)

            # Discard already downloaded unit from the return value.
            named_tuple = model(metadata=unit.metadata, **unit.unit_key).as_named_tuple
            values.discard(named_tuple)

    ret = set()
    ret.update(*sorted_units.values())
    return ret


def get_all_existing_units(search_dicts, unit_fields, unit_type, search_method):
    """
    Get all existing units on the server which match given search_dicts using
    given search_method.

    :param search_dicts:  unit keys generator
    :type search_dicts:   iterator of unit keys
    :param unit_fields:   unit fields to be requested to the search_method
    :type unit_fields:    list or tuple
    :param unit_type:     unit type
    :type unit_type:      basestring
    :param search_method: search method to be used to search for non-repo-specific units
    :type search_method:  a search method accepting a unit type and
                          pulp.server.db.criteria.Criteria as parameters
    :return:              generator of Units found using the search_method
    :rtype:               iterator of pulp.plugins.model.Unit
    """
    # Instead of separate query for each unit, we are using paginate to query
    # for a lot of units at once.
    for segment in paginate(search_dicts):
        unit_filters = {'$or': list(segment)}
        criteria = Criteria(filters=unit_filters, fields=unit_fields)
        for result in search_method(unit_type, criteria):
            yield result


def _sort_by_type(wanted):
    ret = {}
    for unit in wanted:
        ret.setdefault(unit.__class__.__name__, set()).add(unit)
    return ret
