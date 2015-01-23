import ConfigParser
import logging
import os

from pulp.server.db.connection import get_collection


_logger = logging.getLogger('pulp_rpm.plugins.migrations.0019')


def _get_timestamp(distribution):
    """
    Given a distribution unit, tries to get the timestamp from its treeinfo
    file on disk. If any trouble happens, this returns 0.0 as a default, which
    will cause the next sync to re-fetch the treeinfo file.

    :param distribution:    distribution object from the DB that must include
                            the key '_storage_path'
    :type  distribution:    dict

    :return:    timestamp as read from the [general] section of a file named
                either 'treeinfo' or '.treeinfo'. If the file does not exist or
                is not parsable, returns 0.0 as the default.
    :rtype:     float
    """
    parser = ConfigParser.RawConfigParser()
    # the default implementation of this method makes all option names lowercase,
    # which we don't want. This is the suggested solution in the python.org docs.
    parser.optionxform = str

    path = distribution['_storage_path']
    for filename in ('treeinfo', '.treeinfo'):
        try:
            treeinfo_path = os.path.join(path, filename)
            with open(treeinfo_path) as open_file:
                parser.readfp(open_file)
                timestamp = parser.get('general', 'timestamp')
                return float(timestamp)
        except:
            # if anything goes wrong reading 'treeinfo', try '.treeinfo'
            continue
    # this default will ensure that the next sync will re-fetch
    # the treeinfo file, which should correct any problems encountered in reading
    # or parsing the current one
    _logger.warning('problem reading treeinfo file at %s' % path)
    _logger.info('using default timestamp of 0.0 for distribution with bad/missing treeinfo file')
    return 0.0


def migrate(*args, **kwargs):
    """
    Add the timestamp attribute to distribution units. The value comes
    from the treeinfo file.
    """
    dist_collection = get_collection('units_distribution')
    for distribution in dist_collection.find({}, {'_storage_path': 1}):
        timestamp = _get_timestamp(distribution)

        dist_collection.update({'_id': distribution['_id']},
                               {'$set': {'timestamp': timestamp}}, safe=True)
