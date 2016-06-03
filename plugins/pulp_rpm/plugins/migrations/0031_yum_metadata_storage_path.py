from gettext import gettext as _
import logging
import os

from pulp.plugins.migration.standard_storage_path import Plan
from pulp.server.db import connection, model

_log = logging.getLogger('pulp')


def migrate(*args, **kwargs):
    """
    Re-calculate storage path for yum_repo_metadata_file unit
    """
    collection = connection.get_collection('units_yum_repo_metadata_file')
    key_fields = ('data_type', 'repo_id')
    instance = Plan(collection, key_fields)
    repos = set()
    for unit in instance:
        unit.migrate(unit.plan, unit.id, unit.storage_path, unit.new_path)
        repos.add(unit.key['repo_id'])

    repos_to_republish = model.Distributor.objects.filter(repo_id__in=repos,
                                                          last_publish__ne=None)

    path = os.path.join('/var/lib/pulp', '0031_yum_metadata_storage_path.txt')
    f = open(path, 'w')
    f.write(str([repo.repo_id for repo in repos_to_republish]))
    f.close()
    msg = _('***Note. You may want to re-publish the list of repos found in %s.\n'
            '   This migration fixed an issue with wrong yum_repo_metadata_file storage path.'
            % f.name)
    _log.info(msg)
