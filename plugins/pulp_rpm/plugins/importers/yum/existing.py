import logging

from pulp.server.db.model.criteria import Criteria, UnitAssociationCriteria

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.utils import paginate


_LOGGER = logging.getLogger(__name__)


def associate_already_downloaded_units(unit_type, units_to_download, sync_conduit):
    """
    Given a generator of Package instances, this method checks if a package with given
    type and unit key already exists in Pulp. This means that the package is already
    downloaded and just needs to be associated with the given repository.
    After importing already downloaded units to the repository, it returns a generator
    of the remaining Package instances which need to be downloaded.

    :param unit_type:         basestring
    :type  unit_type:         unit type
    :param units_to_download: generator of pulp_rpm.plugins.db.models.Package instances that
                              should be considered for download
    :type  units_to_download: generator
    :param sync_conduit:      sync conduit
    :type  sync_conduit:      pulp.plugins.conduits.repo_sync.RepoSyncConduit

    :return:    generator of pulp_rpm.plugins.db.models.Package instances that
                need to be downloaded
    :rtype:     generator
    """
    model = models.TYPE_MAP[unit_type]
    unit_fields = model.UNIT_KEY_NAMES

    # Instead of separate query for each unit, we are using paginate to query
    # for a lot of units at once.
    for units_page in paginate(units_to_download):
        unit_filters = {'$or': [unit.unit_key for unit in units_page]}
        criteria = Criteria(filters=unit_filters, fields=unit_fields)
        result = sync_conduit.search_all_units(unit_type, criteria)
        result_unit_keys = [unit.unit_key for unit in result]
        for unit in units_page:
            if unit.unit_key in result_unit_keys:
                # Since unit is already downloaded, call respective sync_conduit calls to import
                # the unit in given repository.
                downloaded_unit = sync_conduit.init_unit(unit_type, unit.unit_key,
                                                         unit.metadata, unit.relative_path)
                sync_conduit.save_unit(downloaded_unit)
            else:
                yield unit


def check_repo(wanted, unit_search_method):
    """
    Given an iterable of units as namedtuples, this function will search for them
    using the given search method and return the set of tuples that were not
    found.

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
        fields = model.UNIT_KEY_NAMES

        unit_keys_generator = (unit._asdict() for unit in values.copy())
        for unit in get_existing_units(unit_keys_generator, fields, unit_type, unit_search_method):
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


def _sort_by_type(wanted):
    ret = {}
    for unit in wanted:
        ret.setdefault(unit.__class__.__name__, set()).add(unit)
    return ret
