# -*- coding: utf-8 -*-
# Migration script to set the repoid on pkg group and category units.
#
# Copyright © 2010-2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import copy
import logging
from pymongo.errors import DuplicateKeyError

from pulp.server.managers import factory
from pulp.server.managers.repo.unit_association_query import RepoUnitAssociationQueryManager,UnitAssociationCriteria
from pulp.server.managers.repo.unit_association import RepoUnitAssociationManager
from pulp.server.managers.content.cud import ContentManager
from pulp.plugins.loader import api
from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY

_log = logging.getLogger('pulp')

# Initialize plugin loader api and other managers
api.initialize()
ass_query_mgr =  RepoUnitAssociationQueryManager()
ass_mgr = RepoUnitAssociationManager()
content_mgr = ContentManager()

def _get_repos():
    """
     Lookups all the yum based repos in pulp.
    """
    factory.initialize()
    repos = factory.repo_query_manager().find_with_importer_type("yum_importer")
    if not repos:
        _log.debug("No repos found to perform db migrate")
        return []
    repo_ids = [repo['id'] for repo in repos]
    return repo_ids

def _fix_pkg_group_category_repoid(repoid, typeid):
    """
    Looks up units with in a repo and validate if the repoid in the unit metadata matches the repo
    the unit is associated with. If they dont match,
     * take a deep copy of the pkg group or category unit
     * create(save) new unit with fixed repoid
     * remove association between old unit and repo
     * associate new unit with the repo
    """
    units = ass_query_mgr.get_units(repo_id=repoid, criteria=UnitAssociationCriteria(type_ids=typeid))
    _log.debug("Found %s units in repo %s" % (len(units), repoid))
    for unit in units:
        if unit['metadata']['repo_id'] != repoid:
            _log.debug("Found unit %s to migrate" % unit['id'])
            # take a copy of the unit and fix the repoid
            new_unit = _safe_copy_unit(unit)
            new_unit['metadata']['repo_id'] = repoid
            try:
                content_mgr.add_content_unit(content_type=typeid, unit_id=new_unit['id'], unit_metadata=new_unit['metadata'])
            except DuplicateKeyError:
                # duplicate key, if unit already exists; just continue and associate to the repo; nothing new to create
                _log.debug("A pkg group with id %s and repoid %s already exists, nothing new to create" % (unit['id'], repoid))
                pass
            # unassociate the old unit from the repo
            ass_mgr.unassociate_unit_by_id(repo_id=repoid, unit_type_id=typeid, unit_id=unit['id'], owner_type="user", owner_id="admin")
            # associate the new unit back to the repo
            ass_mgr.associate_unit_by_id(repo_id=repoid, unit_type_id=typeid, unit_id=new_unit['id'], owner_type="user", owner_id="admin")

def _safe_copy_unit(unit):
    """
    Creates a deep copy of the unit and cleans out the _ fields
    @param unit: pulp.plugins.data.Unit object to clone
    @return: cloned unit pulp.plugins.data.Unit
    """
    u = copy.deepcopy(unit)
    u.id = None
    # remove all the _ fields so save_unit defaults them
    for key in u['metadata'].keys():
        if key.startswith('_') :
            del u['metadata'][key]
    return u

def _migrate_units():
    """
    fix the repoid metadata pkg group and category units.
    """
    repoids = _get_repos()
    for repoid in repoids:
        # process package group units
        for typeid in [TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY]:
            _log.debug("Processing repo id %s with type %s" % (repoid, typeid))
            _fix_pkg_group_category_repoid(repoid, typeid)

def migrate(*args, **kwargs):
    _migrate_units()