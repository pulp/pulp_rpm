import logging

from pulp.server.db.connection import get_collection
from pulp.server.db.migrations.lib import utils


_logger = logging.getLogger('pulp_rpm.plugins.migrations.0042')


def migrate(*args, **kwargs):

    erratum_collection = get_collection('units_erratum')
    fields_to_add = ['relogin_suggested', 'restart_suggested']
    for field in fields_to_add:
        total_erratum_units = erratum_collection.count(
            {field: {'$exists': False}})

        with utils.MigrationProgressLog(field + ' field on Erratum',
                                        total_erratum_units) as migration_log:
            for errata in erratum_collection.find(
                    {field: {'$exists': False}},
                    ['errata_id']).batch_size(100):
                erratum_collection.update({'_id': errata['_id']},
                                          {'$set': {field: ''}})
                migration_log.progress()
