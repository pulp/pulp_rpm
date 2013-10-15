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

import os

from pulp.plugins.conduits.repo_sync import RepoSyncConduit
from pulp.plugins.conduits.upload import UploadConduit
from pulp.plugins.conduits.unit_import import ImportUnitConduit
from pulp.plugins.conduits.dependency import DependencyResolutionConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import SyncReport, Unit
import mock


def get_sync_conduit(type_id=None, existing_units=None, pkg_dir=None):
    def build_failure_report(summary, details):
        return SyncReport(False, sync_conduit._added_count, sync_conduit._updated_count,
                          sync_conduit._removed_count, summary, details)

    def build_success_report(summary, details):
        return SyncReport(True, sync_conduit._added_count, sync_conduit._updated_count,
                          sync_conduit._removed_count, summary, details)

    def side_effect(type_id, key, metadata, rel_path):
        if rel_path and pkg_dir:
            rel_path = os.path.join(pkg_dir, rel_path)
            if not os.path.exists(os.path.dirname(rel_path)):
                os.makedirs(os.path.dirname(rel_path))
        unit = Unit(type_id, key, metadata, rel_path)
        return unit

    def get_units(criteria=None):
        ret_val = []
        if existing_units:
            for u in existing_units:
                if criteria:
                    if u.type_id in criteria.type_ids:
                        ret_val.append(u)
                else:
                    ret_val.append(u)
        return ret_val

    def search_all_units(type_id, criteria):
        ret_val = []
        if existing_units:
            for u in existing_units:
                if u.type_id == type_id:
                    if u.unit_key['id'] == criteria['filters']['id']:
                        ret_val.append(u)
        return ret_val

    sync_conduit = mock.Mock(spec=RepoSyncConduit)
    sync_conduit._added_count = sync_conduit._updated_count = sync_conduit._removed_count = 0
    sync_conduit.init_unit.side_effect = side_effect
    sync_conduit.get_units.side_effect = get_units
    sync_conduit.save_unit = mock.Mock()
    sync_conduit.search_all_units.side_effect = search_all_units
    sync_conduit.build_failure_report = mock.MagicMock(side_effect=build_failure_report)
    sync_conduit.build_success_report = mock.MagicMock(side_effect=build_success_report)
    sync_conduit.set_progress = mock.MagicMock()

    return sync_conduit


def get_import_conduit(source_units=None, existing_units=None):
    def get_source_units(criteria=None):
        units = []
        for u in source_units:
            if criteria and u.type_id not in criteria.type_ids:
                continue
            units.append(u)
        return units
    def get_units(criteria=None):
        ret_val = []
        if existing_units:
            for u in existing_units:
                if criteria:
                    if criteria.skip:
                        return []
                    if u.type_id in criteria.type_ids:
                        ret_val.append(u)
                else:
                    ret_val.append(u)
        return ret_val
    def search_all_units(type_id=None, criteria=None):
        ret_val = []
        if existing_units:
            for u in existing_units:
                if u.type_id is None:
                    ret_val.append(u)
                elif u.type_id in ["rpm", "srpm"]:
                    ret_val.append(u)
        return ret_val
    def save_unit(unit):
        units = []
        return units.append(unit)

    def get_repo_scratchpad(repoid=None):
        return {}

    import_conduit = mock.Mock(spec=ImportUnitConduit)
    import_conduit.get_source_units.side_effect = get_source_units
    # import_conduit.get_units.side_effect = get_units
    import_conduit.search_all_units.side_effect = search_all_units
    import_conduit.save_unit = mock.Mock()
    import_conduit.save_unit.side_effect = save_unit
    import_conduit.get_repo_scratchpad = mock.Mock()
    import_conduit.get_repo_scratchpad.side_effect = get_repo_scratchpad
    return import_conduit

def get_upload_conduit(type_id=None, unit_key=None, metadata=None, relative_path=None, pkg_dir=None):
    def side_effect(type_id, unit_key, metadata, relative_path):
        if relative_path and pkg_dir:
            relative_path = os.path.join(pkg_dir, relative_path)
        unit = Unit(type_id, unit_key, metadata, relative_path)
        return unit

    def get_units(criteria=None):
        ret_units = True
        if criteria and hasattr(criteria, "type_ids"):
            if type_id and type_id not in criteria.type_ids:
                ret_units = False
        return []

    upload_conduit = mock.Mock(spec=UploadConduit)
    upload_conduit.init_unit.side_effect = side_effect

    upload_conduit.get_units = mock.Mock()
    upload_conduit.get_units.side_effect = get_units

    upload_conduit.save_units = mock.Mock()
    upload_conduit.save_units.side_effect = side_effect

    upload_conduit.build_failure_report = mock.Mock()
    upload_conduit.build_failure_report.side_effect = side_effect

    upload_conduit.build_success_report = mock.Mock()
    upload_conduit.build_success_report.side_effect = side_effect

    return upload_conduit

def get_dependency_conduit(type_id=None, unit_key=None, metadata=None, existing_units=None, relative_path=None, pkg_dir=None):
    def side_effect(type_id, unit_key, metadata, relative_path):
        if relative_path and pkg_dir:
            relative_path = os.path.join(pkg_dir, relative_path)
        unit = Unit(type_id, unit_key, metadata, relative_path)
        return unit

    def get_units(criteria=None):
        ret_val = []
        if existing_units:
            for u in existing_units:
                if criteria:
                    if criteria.skip:
                        return []
                    if u.type_id in criteria.type_ids:
                        ret_val.append(u)
                else:
                    ret_val.append(u)
        return ret_val

    def get_repo_scratchpad(repoid=None):
        return {}


    dependency_conduit = mock.Mock(spec=DependencyResolutionConduit)
    dependency_conduit.get_units = mock.Mock()
    dependency_conduit.get_units.side_effect = get_units
    dependency_conduit.build_failure_report = mock.Mock()
    dependency_conduit.build_failure_report.side_effect = side_effect

    dependency_conduit.build_success_report = mock.Mock()
    dependency_conduit.build_success_report.side_effect = side_effect

    dependency_conduit.get_repo_scratchpad = mock.Mock()
    dependency_conduit.get_repo_scratchpad.side_effect = get_repo_scratchpad

    return dependency_conduit

def get_basic_config(*arg, **kwargs):
    """

    :param arg:
    :param kwargs:
    :return:
    :rtype: pulp.plugins.config.PluginCallConfiguration
    """
    plugin_config = {"num_retries":0, "retry_delay":0}
    repo_plugin_config = {}
    for key in kwargs:
        repo_plugin_config[key] = kwargs[key]
    config = PluginCallConfiguration(plugin_config,
            repo_plugin_config=repo_plugin_config)
    return config
