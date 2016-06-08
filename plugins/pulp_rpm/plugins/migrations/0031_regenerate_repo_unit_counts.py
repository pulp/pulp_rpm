"""
Migration to regenerate the repo unit counts after a issue 1979 is fixed which caused some of them
to be too high.

https://pulp.plan.io/issues/1979

"""

from pulp.server.db import connection


def rebuild_content_unit_counts(db, repo_id):
    """
    Update the content_unit_counts field on a Repository.

    :param db: The database reference to use
    :type db: pymongo.database.Database
    :param repo_id: The repository id to update
    :type repo_id: basestring
    """
    repos_collection = db['repos']

    pipeline = [
        {'$match': {'repo_id': repo_id}},
        {'$group': {'_id': '$unit_type_id', 'sum': {'$sum': 1}}}]
    q = db.command('aggregate', 'repo_content_units', pipeline=pipeline)

    # Flip this into the form that we need
    counts = {}
    for result in q['result']:
        counts[result['_id']] = result['sum']

    if counts:
        repos_collection.update_one({'repo_id': repo_id}, {'$set': {'content_unit_counts': counts}})


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    repos_collection = db['repos']
    for repo in repos_collection.find():
        repo_id = repo['repo_id']
        rebuild_content_unit_counts(db, repo_id)
