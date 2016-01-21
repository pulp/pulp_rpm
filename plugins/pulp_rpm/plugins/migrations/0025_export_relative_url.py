"""
Migration to normalize relative_url, and populate relative_url on
export distributors
"""
from pulp.server.db import connection


def _find_yum_distributor(distributors):
    """
    Find this repo's 'yum_distributor' to pull the relative_url from.

    While technically you can have more than one yum_distributor...
    functionality really only works for a single distributor at a time.
    This distributor's ID is 'yum_distributor'

    :param distributors: List of distributors for repo.
    :type distributors: list
    """
    for distributor in distributors:
        if distributor['distributor_id'] == 'yum_distributor':
            if 'config' in distributor and 'relative_url' in distributor['config']:
                return distributor
    return None


def _clean_distributors_relative_url(repo_distributors, distributors):
    """
    Cleanup the distributors relative url.  YUM Distributors were generated
    with a leading slash in certain use cases before PR #776, which fixes
    issue #1520

    :param repo_distributors: The repo_distributor collection from mongodb
    :type repo_distributors: pymongo.collection.Collection
    :param distributors: The list of distributors for the repo
    :type distributors: list
    """
    for distributor in distributors:
        if 'config' in distributor and 'relative_url' in distributor['config']\
                and distributor['config']['relative_url'].startswith('/', 0, 1):
            relative_url = distributor['config']['relative_url'].lstrip('/ ')
            distributor['config']['relative_url'] = relative_url
            repo_distributors.update_one({'_id': distributor['_id']},
                                         {'$set': {'config': distributor['config']}})


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    repos = db['repos']
    repo_distributors = db['repo_distributors']
    repo_objects = repos.find({'notes': {'_repo-type': 'rpm-repo'}})
    for repo_object in repo_objects:
        distributors = list(repo_distributors.find({'repo_id': repo_object['repo_id']}))
        _clean_distributors_relative_url(repo_distributors, distributors)
        yum_distributor = _find_yum_distributor(distributors)
        for distributor in distributors:

            if distributor['distributor_type_id'] == 'export_distributor' and \
                    'relative_url' not in distributor['config']:

                if yum_distributor is None:
                    relative_url = repo_object['repo_id']
                else:
                    relative_url = yum_distributor['config']['relative_url']

                distributor['config']['relative_url'] = relative_url

                repo_distributors.update_one({'_id': distributor['_id']},
                                             {'$set': {'config': distributor['config']}})
