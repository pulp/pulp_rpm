from pulp.server.db import connection


def migrate(*args, **kwargs):
    """
    Clean up duplicated collections in erratum pkglist.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    erratum_collection = db['units_erratum']

    for erratum in erratum_collection.find({}, ['pkglist']).batch_size(100):
        migrate_erratum(erratum_collection, erratum)


def migrate_erratum(erratum_collection, erratum):
    """
    Leave only the newest collections in erratum pkglist in case of duplicates.

    The newest collections are determined by their position in pkglist.
    They are at the end of the list.

    :param erratum_collection:  collection of erratum units
    :type  erratum_collection:  pymongo.collection.Collection
    :param erratum:        the erratum unit being migrated
    :type  erratum:        dict
    """
    pkglist = erratum.get('pkglist', [])
    new_pkglist = []
    added_collections = set()

    for collection in pkglist[::-1]:
        coll_name = collection.get('name')
        repo_id = collection.get('_pulp_repo_id')
        coll_id = (coll_name, repo_id)
        if coll_id not in added_collections:
            new_pkglist.append(collection)
            added_collections.add(coll_id)

    # to keep the order of the original pkglist
    new_pkglist = new_pkglist[::-1]
    if pkglist != new_pkglist:
        erratum_collection.update({'_id': erratum['_id']},
                                  {'$set': {'pkglist': new_pkglist}})
