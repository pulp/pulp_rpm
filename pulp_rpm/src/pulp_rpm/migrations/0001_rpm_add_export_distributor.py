
# -*- coding: utf-8 -*-

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

# Migrating all old rpm repositories to have export_distributor along with yum_distributor
import logging

from pulp.server.db.model.repository import RepoDistributor
from pulp_rpm.common import ids

EXPORT_DISTRIBUTOR_CONFIG = {"http" : False, "https" : True}

_LOG = logging.getLogger('pulp')

def _migrate_rpm_repositories():
    '''
    This migration takes care of adding export_distributor to all the old rpm repos 
    with no export_distributor already associated to them. Since we have renamed iso_distributor
    to export_distributor, it also removes iso_distributor associated with an rpm repo.  
    '''
    collection = RepoDistributor.get_collection()
    for repo_distributor in collection.find():

        # Check only for rpm repos
        if repo_distributor['distributor_type_id'] == ids.TYPE_ID_DISTRIBUTOR_YUM:

            # Check if an export_distributor exists for the same repo
            if collection.find_one({'repo_id': repo_distributor['repo_id'], 'distributor_type_id': ids.TYPE_ID_DISTRIBUTOR_EXPORT}) is None:

                # If not, create a new one with default config
                export_distributor = RepoDistributor(repo_id = repo_distributor['repo_id'], 
                                                  id = ids.EXPORT_DISTRIBUTOR_ID,
                                                  distributor_type_id = ids.TYPE_ID_DISTRIBUTOR_EXPORT, 
                                                  config = EXPORT_DISTRIBUTOR_CONFIG, 
                                                  auto_publish = False)
                collection.save(export_distributor, safe=True)
            
            # Remove iso_distributor associated with the repo 
            iso_distributor = collection.find_one({'repo_id': repo_distributor['repo_id'], 'distributor_type_id': 'iso_distributor'})
            if iso_distributor is not None:
                collection.remove(iso_distributor, safe=True)

def migrate(*args, **kwargs):
    _LOG.info("Export distributor migration for rpm repositories started")
    _migrate_rpm_repositories()
    _LOG.info("Export distributor migration for rpm repositories finished")
