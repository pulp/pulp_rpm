from collections import defaultdict

from pymongo.errors import DuplicateKeyError

from pulp.server.db import connection
from pulp.server.db.migrations.lib import utils

REPO_ID_KEY = '_pulp_repo_id'


def migrate(*args, **kwargs):
    """
    Move erratum pkglists to a separate collection.

    It is safe to run this migration multiple times.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    erratum_collection = db['units_erratum']
    pkglist_collection = db['erratum_pkglists']

    total_erratum_units = erratum_collection.count()

    with utils.MigrationProgressLog('Erratum', total_erratum_units) as migration_log:
        for erratum in erratum_collection.find({}, ['errata_id', 'pkglist']).batch_size(100):
            migrate_erratum_pkglist(erratum_collection, pkglist_collection, erratum)
            migration_log.progress()


def migrate_erratum_pkglist(erratum_collection, pkglist_collection, erratum):
    """
    Move pkglists to a new collection.
    Remove pkglists from the erratum collection.

    :param erratum_collection: collection of erratum units
    :type  erratum_collection: pymongo.collection.Collection
    :param pkglists_collection: collection of erratum pkglists
    :type  pkglists_collection: pymongo.collection.Collection
    :param erratum: the erratum unit being migrated
    :type  erratum: dict
    """
    collections_to_migrate = defaultdict(list)
    erratum_pkglists = []
    seen_collections = set()

    existing_pkglist = erratum.get('pkglist', [])
    errata_id = erratum['errata_id']

    if not existing_pkglist:
        # pkglist was migrated before
        return

    for collection in reversed(existing_pkglist):
        filenames = tuple(pkg['filename'] for pkg in collection.get('packages', []))
        if filenames not in seen_collections:
            seen_collections.add(filenames)
            if REPO_ID_KEY in collection:
                repo_id = collection.pop(REPO_ID_KEY)
            else:
                repo_id = ''

            # there could be multiple collections for the same repo in a pkglist,
            # so we need to collect them first
            collections_to_migrate[repo_id].append(collection)

    for repo_id, collections in collections_to_migrate.items():
        new_pkglist = {'errata_id': errata_id,
                       'repo_id': repo_id,
                       'collections': collections}
        erratum_pkglists.append(new_pkglist)

    try:
        pkglist_collection.insert(erratum_pkglists)
    except DuplicateKeyError:
        # migration was run before and pkglist was migrated
        # but it was not deleted from erratum collection for some reason
        pass

    # pkglist in erratum collection is no longer needed
    erratum_collection.update_one({'_id': erratum['_id']},
                                  {'$set': {'pkglist': []}})
