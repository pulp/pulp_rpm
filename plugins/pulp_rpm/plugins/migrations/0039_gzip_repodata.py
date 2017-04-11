import gzip
import logging

import bson

from pulp.server.db import connection


_logger = logging.getLogger(__name__)


def migrate(*args, **kwargs):
    """
    Compress the content of repodata field for RPM and SRPM units.
    Migration can be safely re-run multiple times.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    rpm_collection = db['units_rpm']
    srpm_collection = db['units_srpm']

    total_rpm_units = rpm_collection.count()
    total_srpm_units = srpm_collection.count()

    msg = '* NOTE: This migration may take some time depending on the size of your Pulp content. *'
    stars = '*' * len(msg)
    progress_msg = '* Migrated units: %s of %s'

    _logger.info(stars)
    _logger.info(msg)
    _logger.info(stars)

    if total_rpm_units:
        _logger.info('* Migrating RPM content...')

    migrated_units = 0
    for rpm in rpm_collection.find({}, ['repodata']).batch_size(100):
        migrate_rpm_base(rpm_collection, rpm)

        migrated_units += 1
        another_ten_percent_completed = total_rpm_units >= 10 and \
            not migrated_units % (total_rpm_units // 10)
        all_units_migrated = migrated_units == total_rpm_units
        if another_ten_percent_completed or all_units_migrated:
            _logger.info(progress_msg % (migrated_units, total_rpm_units))

    if total_srpm_units:
        _logger.info('* Migrating SRPM content...')

    migrated_units = 0
    for srpm in srpm_collection.find({}, ['repodata']).batch_size(100):
        migrate_rpm_base(srpm_collection, srpm)

        migrated_units += 1
        another_ten_percent_completed = total_srpm_units >= 10 and \
            not migrated_units % (total_srpm_units // 10)
        all_units_migrated = migrated_units == total_srpm_units
        if another_ten_percent_completed or all_units_migrated:
            _logger.info(progress_msg % (migrated_units, total_srpm_units))

    _logger.info(stars)


def migrate_rpm_base(collection, unit):
    """
    Compress 'primary', 'other' and 'filelists' metadata for a given unit.

    Compressed metadata is stored in DB as a binary type.
    For each metadata migration is performed only if the metadata is still a string and
    not yet of a binary type.

    :param collection:  collection of RPM units
    :type  collection:  pymongo.collection.Collection
    :param unit:        the RPM unit being migrated
    :type  unit:        dict
    """
    delta = {'repodata': {}}
    for metadata_type in ['primary', 'other', 'filelists']:
        metadata = unit['repodata'].get(metadata_type)
        if metadata and not isinstance(metadata, bson.binary.Binary):
            compressed_data = gzip.zlib.compress(metadata.encode('utf-8'))
            delta['repodata'][metadata_type] = bson.binary.Binary(compressed_data)
    if delta['repodata']:
        collection.update_one({'_id': unit['_id']}, {'$set': delta})
