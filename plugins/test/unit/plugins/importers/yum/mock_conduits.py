"""
This module mimics the pulp.plugins.conduits package by creating a number of
closures that can be wrapped by mock objects that will more or less "do the
right thing" for testing purposes.
"""

import os

import mock
from pulp.plugins.conduits import repo_publish, repo_sync, unit_import
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Unit, PublishReport


def plugin_call_config(**kwargs):
    plugin_config = {'num_retries': 0, 'retry_delay': 0}
    repo_plugin_config = kwargs
    return PluginCallConfiguration(plugin_config, repo_plugin_config)


def repo_publish_conduit(repo_scratchpad=None, distributor_scratchpad=None, existing_units=None):
    # closure variables

    repo_scratchpad = repo_scratchpad or {}
    distributor_scratchpad = distributor_scratchpad or {}
    existing_units = existing_units or []

    # closure methods

    get_repo_scratchpad, set_repo_scratchpad = repo_scratch_pad_mixin(repo_scratchpad)

    get_scratchpad, set_scratchpad = generic_scratchpad_mixin(distributor_scratchpad)

    set_progress = status_mixin()

    get_units = single_repo_units_mixin(existing_units)

    build_success_report, build_failure_report = publish_report_mixin()

    def last_publish():
        return None

    # build the mock conduit out of the closures

    conduit = mock.Mock(spec=repo_publish.RepoPublishConduit)

    conduit.get_repo_scratchpad = mock.Mock(wraps=get_repo_scratchpad)
    conduit.set_repo_scratchpad = mock.Mock(wraps=set_repo_scratchpad)
    conduit.get_scratchpad = mock.Mock(wraps=get_scratchpad)
    conduit.set_scratchpad = mock.Mock(wraps=set_scratchpad)
    conduit.set_progress = mock.Mock(wraps=set_progress)
    conduit.get_units = mock.Mock(wraps=get_units)
    conduit.build_success_report = mock.Mock(wraps=build_success_report)
    conduit.build_failure_report = mock.Mock(wraps=build_failure_report)
    conduit.last_publish = mock.Mock(wraps=last_publish)

    return conduit


def repo_group_publish_conduit(multiple_repo_scratchpads=None, group_distributor_scratchpad=None,
                               existing_units_by_repo=None):
    # closure variables

    multiple_repo_scratchpads = multiple_repo_scratchpads or {}
    group_distributor_scratchpad = group_distributor_scratchpad or {}
    existing_units_by_repo = existing_units_by_repo or {}

    # closure methods

    get_scratchpad, set_scratchpad = generic_scratchpad_mixin(group_distributor_scratchpad)

    set_progress = status_mixin()

    get_units = multiple_repo_units_mixin(existing_units_by_repo)

    build_success_report, build_failure_report = publish_report_mixin()

    get_repo_scratchpad = repo_scratchpad_read_mixin(multiple_repo_scratchpads)

    def last_publish():
        return None

    # build the mock conduit out of the closures

    conduit = mock.Mock(spec=repo_publish.RepoGroupPublishConduit)

    conduit.get_repo_scratchpad = mock.Mock(wraps=get_repo_scratchpad)
    conduit.get_scratchpad = mock.Mock(wraps=get_scratchpad)
    conduit.set_scratchpad = mock.Mock(wraps=set_scratchpad)
    conduit.set_progress = mock.Mock(wraps=set_progress)
    conduit.get_units = mock.Mock(wraps=get_units)
    conduit.build_success_report = mock.Mock(wraps=build_success_report)
    conduit.build_failure_report = mock.Mock(wraps=build_failure_report)
    conduit.last_publish = mock.Mock(wraps=last_publish)

    return conduit


# -- sync conduits -------------------------------------------------------------

def repo_sync_conduit(working_dir, repo_scratchpad=None, importer_scratchpad=None,
                      existing_units=None, linked_units=None, repo_id=None):
    # closure variables

    repo_scratchpad = repo_scratchpad or {}
    importer_scratchpad = importer_scratchpad or {}
    existing_units = existing_units or []
    linked_units = linked_units or []

    # closure methods

    get_repo_scratchpad, set_repo_scratchpad = repo_scratch_pad_mixin(repo_scratchpad)

    get_scratchpad, set_scratchpad = generic_scratchpad_mixin(importer_scratchpad)

    init_unit, save_unit, link_unit = add_unit_mixin(working_dir, existing_units, linked_units)

    get_units = single_repo_units_mixin(existing_units)

    search_all_units = search_units_mixin(existing_units)

    set_progress = status_mixin()

    def remove_unit(unit):
        if unit in existing_units:
            existing_units.remove(unit)

    # build the mock conduit out of the closures

    conduit = mock.Mock(spec=repo_sync.RepoSyncConduit)

    conduit.get_repo_scratchpad = mock.Mock(wraps=get_repo_scratchpad)
    conduit.set_repo_scratchpad = mock.Mock(wraps=set_repo_scratchpad)
    conduit.get_scratchpad = mock.Mock(wraps=get_scratchpad)
    conduit.set_scratchpad = mock.Mock(wraps=set_scratchpad)
    conduit.init_unit = mock.Mock(wraps=init_unit)
    conduit.save_unit = mock.Mock(wraps=save_unit)
    conduit.link_unit = mock.Mock(wraps=link_unit)
    conduit.get_units = mock.Mock(wraps=get_units)
    conduit.set_progress = mock.Mock(wraps=set_progress)
    conduit.search_all_units = mock.Mock(wraps=search_all_units)
    conduit.remove_unit = mock.Mock(wraps=remove_unit)
    conduit.repo_id = repo_id

    return conduit


# -- import conduits -----------------------------------------------------------

def import_unit_conduit(working_dir, repo_scratchpad=None, importer_scratchpad=None,
                        existing_units=None, linked_units=None, source_units=None):
    # closure variables

    repo_scratchpad = repo_scratchpad or {}
    importer_scratchpad = importer_scratchpad or {}
    existing_units = existing_units or []
    linked_units = linked_units or []
    source_units = source_units or []

    # closure methods

    get_scratchpad, set_scratchpad = generic_scratchpad_mixin(importer_scratchpad)

    get_repo_scratchpad, set_repo_scratchpad = repo_scratch_pad_mixin(repo_scratchpad)

    get_units = single_repo_units_mixin(existing_units)

    search_all_units = search_units_mixin(existing_units)

    init_unit, save_unit, link_unit = add_unit_mixin(working_dir, existing_units, linked_units)

    get_source_units = single_repo_units_mixin(source_units)

    def associate_unit(unit):
        if unit not in existing_units:
            existing_units.append(unit)

    # build the mock conduit out of the closures

    conduit = mock.Mock(spec=unit_import.ImportUnitConduit)

    conduit.get_scratchpad = mock.Mock(wraps=get_scratchpad)
    conduit.set_scratchpad = mock.Mock(wraps=set_scratchpad)
    conduit.get_repo_scratchpad = mock.Mock(wraps=get_repo_scratchpad)
    conduit.set_repo_scratchpad = mock.Mock(wraps=set_repo_scratchpad)
    conduit.get_units = mock.Mock(wraps=get_units)
    conduit.search_all_units = mock.Mock(wraps=search_all_units)
    conduit.init_unit = mock.Mock(wraps=init_unit)
    conduit.save_unit = mock.Mock(wraps=save_unit)
    conduit.link_unit = mock.Mock(wraps=link_unit)
    conduit.associate_unit = mock.Mock(wraps=associate_unit)
    conduit.get_source_units = mock.Mock(wraps=get_source_units)

    return conduit


# -- mixin closures ------------------------------------------------------------

def repo_scratch_pad_mixin(repo_scratchpad):
    def get_repo_scratchpad():
        return repo_scratchpad

    def set_repo_scratchpad(value):
        repo_scratchpad.clear()
        repo_scratchpad.update(value)

    return get_repo_scratchpad, set_repo_scratchpad


def repo_scratchpad_read_mixin(multiple_repo_scratchpads):
    def get_repo_scratchpad(repo_id):
        scratchpad = multiple_repo_scratchpads.setdefault(repo_id, {})
        return scratchpad

    return get_repo_scratchpad


def single_repo_units_mixin(existing_units):
    def get_units(criteria=None):
        if criteria is None:
            return existing_units[:]
        matched_units = []
        for unit in existing_units:
            if criteria.type_ids and unit.type_id not in criteria.type_ids:
                continue
            if criteria.unit_filters:
                if unit.type_id == 'erratum':
                    start_date = criteria.unit_filters['issued']['$gte']
                    end_date = criteria.unit_filters['issued']['$lte']
                    if not start_date <= unit.metadata['issued'] <= end_date:
                        continue
            matched_units.append(unit)
        if criteria.skip is not None:
            matched_units = matched_units[criteria.skip:]
        if criteria.limit is not None:
            matched_units = matched_units[:criteria.limit]
        return matched_units

    return get_units


def multiple_repo_units_mixin(existing_units_by_repo):
    def get_units(repo_id, criteria):
        existing_units = existing_units_by_repo.setdefault(repo_id, [])
        single_repo_get_units = single_repo_units_mixin(existing_units)
        return single_repo_get_units(criteria)

    return get_units


def search_units_mixin(existing_units):
    def search_all_units(type_id, criteria):
        matched_units = []
        for unit in existing_units:
            if unit.type_id != type_id:
                continue
            if criteria.filters:
                if unit.type_id == 'erratum':
                    start_date = criteria.filters['issued']['$gte']
                    end_date = criteria.filters['issued']['$lte']
                    if not start_date <= unit.metadata['issued'] <= end_date:
                        continue
            matched_units.append(unit)
        if criteria.skip is not None:
            matched_units = matched_units[criteria.skip:]
        if criteria.limit is not None:
            matched_units = matched_units[:criteria.limit]
        return matched_units

    return search_all_units


def generic_scratchpad_mixin(scratchpad):
    def get_scratchpad():
        return scratchpad

    def set_scratchpad(value):
        scratchpad.clear()
        scratchpad.update(value)

    return get_scratchpad, set_scratchpad


def add_unit_mixin(working_dir, existing_units, linked_units):
    def init_unit(type_id, unit_key, metadata, relative_path):
        storage_path = os.path.join(working_dir, relative_path)
        storage_dir = os.path.dirname(storage_path)
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        unit = Unit(type_id, unit_key, metadata, storage_path)
        return unit

    def save_unit(unit):
        if unit not in existing_units:
            existing_units.append(unit)

    def link_unit(from_unit, to_unit, bidirectional=False):
        unit_tuple = (from_unit, to_unit)
        if unit_tuple not in linked_units:
            linked_units.append(unit_tuple)
        if bidirectional:
            link_unit(to_unit, from_unit, False)

    return init_unit, save_unit, link_unit


def status_mixin():
    def set_progress(status):
        pass

    return set_progress


def publish_report_mixin():
    def build_success_report(summary, details):
        return PublishReport(True, summary, details)

    def build_failure_report(summary, details):
        return PublishReport(False, summary, details)

    return build_success_report, build_failure_report
