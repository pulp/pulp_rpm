import glob
import logging
import os
import shutil
import tempfile

import lxml.etree as le

from pulp.server.config import config
from pulp.server.db.connection import get_collection


_logger = logging.getLogger(__file__)


def _move_nested_drpm_dir(repo_dir):
    """
    If a repository has a nested <repo_dir>/drpm/drpm/ directory,
    remove one of the nestings as it should not have been created.
    The invalid nesting was created with publishes between 2.4 & 2.6.

    :param repo_dir: The root directory of the repository
    :type repo_dir: str
    """
    drpm_dir = os.path.join(repo_dir, 'drpms', 'drpms')
    target_drpm_dir = os.path.join(repo_dir, 'drpms')
    if os.path.exists(drpm_dir):
        _logger.debug('Cleaning double drpm dir: %s' % drpm_dir)
        tempdir = tempfile.mkdtemp(dir=repo_dir)
        shutil.move(drpm_dir, tempdir)
        shutil.rmtree(target_drpm_dir)
        shutil.move(os.path.join(tempdir, 'drpms'), repo_dir)
        shutil.rmtree(tempdir)


def _remove_prestodelta_repo_units():
    """
    Remove all prestodelta repo_content_units since they should not have been created
    to begin with.
    """
    metadata_collection = get_collection('units_yum_repo_metadata_file')
    repo_units_collection = get_collection('repo_content_units')
    for presto_unit in metadata_collection.find({'data_type': 'prestodelta'}):
        # remove any repo repo units that reference it, the unit itself will
        # be removed by the orphan cleanup at some point in the future
        repo_units_collection.remove({'unit_id': presto_unit['_id']})


def _remove_prestodelta_from_repomd(repo_dir, prestodelta_name):
    """
    For a given prestodelta filename, remove references to it from
    the repomd.xml file for a repository.

    :param repo_dir: The root directory of the repository to process
    :type repo_dir: str
    :param prestodelta_name: The filename of the prestodelta file
    :type prestodelta_name: str
    """
    repomd = os.path.join(repo_dir, 'repodata', 'repomd.xml')
    presto_name = os.path.join('repodata', prestodelta_name)
    if os.path.exists(repomd):
        tree = le.parse(repomd)
        xpath_str = ".//*[@href='%s']" % presto_name
        root = tree.getroot()
        for bad in tree.findall(xpath_str):
            bad_parent = bad.getparent()
            root.remove(bad_parent)

        with open(repomd, 'w') as handle:
            handle.write(le.tostring(root))


def _remove_prestodelta_symlinks(repo_dir):
    """
    Remove all the prestodelta symlinks from the repodata directory of the given repo.
    In addition, links to the bad prestodelta files will be removed from the repomd.
    Only symlinked prestodeltas are examined since they are links to content units.

    :param repo_dir: The root of the repository
    :type repo_dir: str
    """
    # remove xml entries from the repomd that match the symlinks we removed
    repodata_dir = os.path.join(repo_dir, 'repodata')
    for file_name in glob.glob(os.path.join(repodata_dir, '*prestodelta*')):
        if os.path.islink(file_name):
            os.unlink(file_name)
            # remove the links from the repomd.xml
            base_file_name = os.path.basename(file_name)
            _remove_prestodelta_from_repomd(repo_dir, base_file_name)


def _repo_directories(starting_dir):
    """
    Generator to find all of the repository directories under a given starting directory.

    :param starting_dir: The directory to search
    :type starting_dir: str
    """
    for dir_name, subdir_list, file_list in os.walk(starting_dir):
        if os.path.basename(dir_name) == 'repodata':
            repomd = os.path.join(dir_name, 'repomd.xml')
            if os.path.exists(repomd) and not os.path.islink(repomd):
                # We check for a islink here in case we found a repository
                # that was nested via the treeinfo file.  In that case
                # the repomd.xml will be a link back to a file in the content directory
                # and should be skipped
                repodir = os.path.abspath(os.path.join(dir_name, os.pardir))
                yield repodir


def migrate(*args, **kwargs):
    """
    Fix the drpm directories and broken repomd.xml files.
    """
    # skip this migration if we have no drpm units
    drpm_collection = get_collection('units_drpm')
    if drpm_collection.count() == 0:
        _logger.info('Skipping drpm directory migration since there are no drpm units')
        return

    storage_dir = config.get('server', 'storage_dir')
    master_dir = os.path.join(storage_dir, 'published', 'yum', 'master')

    if os.path.exists(master_dir):
        for repo_dir in _repo_directories(master_dir):
            _logger.debug('Removing bad prestodelta units from %s' % repo_dir)
            _move_nested_drpm_dir(repo_dir)
            _remove_prestodelta_symlinks(repo_dir)

    # Clear out the database
    _remove_prestodelta_repo_units()
