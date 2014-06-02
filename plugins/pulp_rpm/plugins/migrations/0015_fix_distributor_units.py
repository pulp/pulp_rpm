# -*- coding: utf-8 -*-
# Migration script for removing repomd.xml from synced distributions

import logging
import os

from pulp.server.db.connection import get_collection
from pulp.server import config as pulp_config

from pulp_rpm.plugins.importers.yum.parse import treeinfo

_logger = logging.getLogger('pulp_rpm.plugins.migrations.0015')


def _fix_treeinfo_files(distribution_dir):
    """
    find all treeinfo or .treeinfo files in the distribution directory and
    strip any references to repomd.xml in checksum lists.

    Pulp 2.4 does this stripping when saving new treeinfo files but we need do
    a one-time pass of existing files during the upgrade process.
    """
    for root, dirs, files in os.walk(distribution_dir):
        for fname in files:
            if fname.startswith('treeinfo') or fname.startswith('.treeinfo'):
                treeinfo_file = os.path.join(root, fname)
                _logger.info("stripping repomd.xml checksum from %s" % treeinfo_file)
                treeinfo.strip_treeinfo_repomd(treeinfo_file)


def _fix_distribution_units(dist_collection):
    """
    given a collection of distribution units, strip any file references to
    "repodata/repomd.xml" and update the unit record.

    This is a file that Pulp generates, the version from the upstream repo
    should not be kept since it interferes with Pulp's version of the file.
    """
    distributions = dist_collection.find({'files': {"$exists": True}})
    _logger.info("examining distribution units")
    for distribution in distributions:
        for file in distribution['files']:
            if file['downloadurl'].endswith('repodata/repomd.xml'):
                distribution['files'].remove(file)
        dist_collection.update({'_id': distribution['_id']},
                               {'$set': {"files": distribution['files']}}, safe=True)


def migrate(*args, **kwargs):
    """
    finds all treeinfo files and modifies them to remove repomd.xml checksum
    entries. Then, removes any repomd.xml files from distribution units.

    note that this will leave the old repomd.xml files in the content/
    directory. They will get cleaned up on the next repo sync.

    This is related to #1099600 and #1095829
    """
    storage_dir = pulp_config.config.get('server', 'storage_dir')
    distribution_dir = os.path.join(storage_dir, 'content', 'distribution')
    _fix_treeinfo_files(distribution_dir)

    dist_collection = get_collection('units_distribution')
    _fix_distribution_units(dist_collection)
