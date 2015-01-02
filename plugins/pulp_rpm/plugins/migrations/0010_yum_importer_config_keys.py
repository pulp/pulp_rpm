# -*- coding: utf-8 -*-

from pulp.server.db.connection import get_collection


def migrate(*args, **kwargs):
    """
    Migrate existing yum importers to use the new configuration key names.

    This migration has the consolidation of verify_checksum and verify_size into a single
    config value. For simplicity, the value for verify_checksum is used as the new setting
    and verify_size is discarded.

    The newest flag in the old config was redundant; the num_old_packages serves the
    same purpose. The newest flag is discarded.

    The purge_orphaned flag was a carry over from v1 and has no effect. It's documented in
    the old yum importer but I'm not sure it was actually used. This migration will attempt
    to delete it anyway just in case.
    """

    repo_importers = get_collection('repo_importers')

    rename_query = {'$rename': {
        'config.feed_url': 'config.feed',
        'config.ssl_verify': 'config.ssl_validation',
        'config.proxy_url': 'config.proxy_host',
        'config.proxy_user': 'config.proxy_username',
        'config.proxy_pass': 'config.proxy_password',
        'config.num_threads': 'config.max_downloads',
        'config.verify_checksum': 'config.validate',  # see comment above
        'config.remove_old': 'config.remove_missing',
        'config.num_old_packages': 'config.retain_old_count',
    }}
    repo_importers.update({'importer_type_id': 'yum_importer'}, rename_query, safe=True, multi=True)

    remove_query = {'$unset': {'config.newest': 1,
                               'config.verify_size': 1,
                               'config.purge_orphaned': 1}}
    repo_importers.update({'importer_type_id': 'yum_importer'}, remove_query, safe=True, multi=True)
