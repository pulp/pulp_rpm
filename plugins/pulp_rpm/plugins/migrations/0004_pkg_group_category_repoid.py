# -*- coding: utf-8 -*-
# Migration script to set the repoid on pkg group and category units.

import copy
import logging

import pymongo.errors
from pulp.server.managers import factory
from pulp.server.managers.repo.cud import RepoContentUnit
from pulp.server.managers.repo.unit_association_query import UnitAssociationCriteria

from pulp_rpm.common import ids


_log = logging.getLogger('pulp')

# Initialize plugin loader api and other managers
factory.initialize()
ass_query_mgr = factory.repo_unit_association_query_manager()
ass_mgr = factory.repo_unit_association_manager()
content_mgr = factory.content_manager()
repo_mgr = factory.repo_manager()


def _get_repos():
    """
     Lookups all the yum based repos in pulp.
     @return a list of repoids
    """
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
     * re-associate new unit with the repo
    """
    units = ass_query_mgr.get_units(repo_id=repoid,
                                    criteria=UnitAssociationCriteria(type_ids=typeid))
    for unit in units:
        if unit['metadata']['repo_id'] != repoid:
            _log.debug("Found unit %s to migrate" % unit['id'])
            # take a copy of the unit and fix the repoid
            new_unit_metadata = _safe_copy_unit(unit['metadata'])
            new_unit_metadata['repo_id'] = repoid
            try:
                new_unit_id = content_mgr.add_content_unit(content_type=typeid, unit_id=None,
                                                           unit_metadata=new_unit_metadata)
                # Grab the association doc itself from the DB directly
                association = RepoContentUnit.get_collection().find_one({'_id': unit['_id']})
                # Update to point to the new unit
                association['unit_id'] = new_unit_id
                # Save it back to the DB
                RepoContentUnit.get_collection().save(association, safe=True)
            except pymongo.errors.DuplicateKeyError:
                # If migrating this Unit to have the correct repo_id causes a duplicate,
                # then there already
                # is a Unit that has the correct metadata in place in this repository. Because of
                #  this, we
                # should remove the association of the unit with the repository
                RepoContentUnit.get_collection().remove({'_id': unit['_id']})
                # Since we removed a Unit from the repo, we should decrement the repo unit count
                repo_mgr.update_unit_count(repoid, typeid, -1)


def _safe_copy_unit(unit):
    """
    Creates a deep copy of the unit and cleans out the _ fields
    @param unit: unit metadata dict
    @return: cloned unit metadata dict
    """
    u = copy.deepcopy(unit)
    # remove all the _ fields so save_unit defaults them
    for key in u.keys():
        if key.startswith('_'):
            del u[key]
    return u


def _migrate_units():
    """
    fix the repoid metadata pkg group and category units.
    """
    repoids = _get_repos()
    for repoid in repoids:
        # process package group units
        for typeid in [ids.TYPE_ID_PKG_GROUP, ids.TYPE_ID_PKG_CATEGORY]:
            _log.debug("Processing repo id %s with type %s" % (repoid, typeid))
            _fix_pkg_group_category_repoid(repoid, typeid)


def migrate(*args, **kwargs):
    _migrate_units()
