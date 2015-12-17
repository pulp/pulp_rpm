# -*- coding: utf-8 -*-

# Migrating all old rpm repositories to have export_distributor along with yum_distributor
import logging

from pulp.server.db.connection import get_collection
from pulp.server.db import model

from pulp_rpm.common import ids


EXPORT_DISTRIBUTOR_CONFIG = {"http": False, "https": True}

_LOG = logging.getLogger('pulp')


def _migrate_rpm_repositories():
    '''
    This migration takes care of adding export_distributor to all the old rpm repos
    with no export_distributor already associated to them. Since we have renamed iso_distributor
    to export_distributor, it also removes iso_distributor associated with an rpm repo.
    '''
    collection = get_collection('repo_distributors')
    for repo_distributor in collection.find():

        # Check only for rpm repos
        if repo_distributor['distributor_type_id'] == ids.TYPE_ID_DISTRIBUTOR_YUM:

            # Check if an export_distributor exists for the same repo
            if collection.find_one({'repo_id': repo_distributor['repo_id'],
                                    'distributor_type_id': ids.TYPE_ID_DISTRIBUTOR_EXPORT}) is None:
                # If not, create a new one with default config
                export_distributor = model.Distributor(
                    repo_id=repo_distributor['repo_id'],
                    distributor_id=ids.EXPORT_DISTRIBUTOR_ID,
                    distributor_type_id=ids.TYPE_ID_DISTRIBUTOR_EXPORT,
                    config=EXPORT_DISTRIBUTOR_CONFIG,
                    auto_publish=False)
                collection.save(export_distributor)

            # Remove iso_distributor associated with the repo
            iso_distributor = collection.find_one(
                {'repo_id': repo_distributor['repo_id'], 'distributor_type_id': 'iso_distributor'})
            if iso_distributor is not None:
                collection.remove(iso_distributor)


def migrate(*args, **kwargs):
    _LOG.info("Export distributor migration for rpm repositories started")
    _migrate_rpm_repositories()
    _LOG.info("Export distributor migration for rpm repositories finished")
