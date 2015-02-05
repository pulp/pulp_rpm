import logging
import os

from pulp.common.config import read_json_config
from pulp_rpm.plugins.distributors.yum import configuration
from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM


_logger = logging.getLogger(__name__)


CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % TYPE_ID_DISTRIBUTOR_YUM
config = read_json_config(CONF_FILE_PATH)

def walk_and_clean_directories(base_directory):
    """
    Walk through all of the directories inside of the base dir and clean the orphaned directories.
    The leaves should be directories with a listing file and a symlink. If there is no symlink,
    the directory is part of the relative url of a repo that has been deleted and it should be
    removed.

    :param base_directory: directory to search for orphaned directories
    :type  base_directory: str

    :raises: OSError can occur if migration occurs durring a concurrent publish
    """

    for path, dirs, files in os.walk(base_directory):
        is_orphan = not dirs and (files == ['listing'] or files == [])
        if is_orphan and path != base_directory:
            clean_simple_hosting_directories(path, base_directory)

def clean_simple_hosting_directories(leaf, containing_dir):
    """
    Recursively clean the directory structure starting with an orphaned leaf and stopping when
    the directory is no longer an orphan or is outside of the containing_dir. Does not remove
    anything outside of the containing directory. The dirs are artifacts of the relative paths of
    repos that were deleted.

    :param leaf: path to a leaf directory
    :type  leaf: str
    :param containing_dir: path to the location of published repos
    :type  containing_dir: str
    """

    # This function is potentially dangerous so it is important to restrict it to the
    # containing dir, which should be the publish directories.
    if containing_dir not in os.path.dirname(leaf):
        return

    # If the only file is the listing file, it is safe to delete the file and containing dir.
    if os.listdir(leaf) == ['listing']:
        listing_path = os.path.join(leaf, 'listing')
        _logger.debug("Cleaning up orphaned listing file: %s" % listing_path)
        os.remove(listing_path)

    # Some leafs may have a listing file, some may not.
    if os.listdir(leaf) == []:
        # We do not need to check for concurrent delete on migration.
        _logger.debug("Cleaning up orphaned directory: %s" % leaf)
        os.rmdir(leaf)

    up_dir = os.path.dirname(leaf)
    clean_simple_hosting_directories(up_dir, containing_dir)

def migrate():
    """Clean up published orphaned directory structure."""
    _logger.debug("Cleaning up published https yum directories.")
    walk_and_clean_directories(configuration.get_https_publish_dir(config))
    _logger.debug("Cleaning up published yum http yum directories.")
    walk_and_clean_directories(configuration.get_http_publish_dir(config))
