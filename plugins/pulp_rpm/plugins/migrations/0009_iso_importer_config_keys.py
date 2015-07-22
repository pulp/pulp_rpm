from pulp.server.db.connection import get_collection


def migrate(*args, **kwargs):
    """
    Migrate existing ISOImporters to use the new configuration key names.
    """
    repo_importers = get_collection('repo_importers')
    # This query changes the names of some of the importer keys to be the new names
    rename_query = {'$rename': {
        'config.feed_url': 'config.feed',
        'config.num_threads': 'config.max_downloads',
        # proxy_url was technically just a hostname in the past. it was a badly named parameter.
        'config.proxy_url': 'config.proxy_host',
        'config.proxy_user': 'config.proxy_username',
        'config.remove_missing_units': 'config.remove_missing',
        'config.validate_units': 'config.validate',
    }}
    repo_importers.update({'importer_type_id': 'iso_importer'}, rename_query, safe=True, multi=True)
