"""
The new distributor now stores the master copy of a published repository outside
of the distributor's working directory. It also stores the published repositories
in a new location.

This script cleans up all of the aforementioned directories and re-publishes the
corresponding repositories.
"""

import os
import shutil

from pulp.common.config import read_json_config
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.loader import api
from pulp.server import config as pulp_config
from pulp.server.db import model
from pulp.server.db.connection import get_collection

from pulp_rpm.plugins.distributors.yum.publish import Publisher


YUM_DISTRIBUTOR_ID = 'yum_distributor'

REPO_WORKING_DIR = '/var/lib/pulp/working/%s/distributors/' + YUM_DISTRIBUTOR_ID

OLD_ROOT_PUBLISH_DIR = '/var/lib/pulp/published'
OLD_HTTP_PUBLISH_DIR = os.path.join(OLD_ROOT_PUBLISH_DIR, 'http', 'repos')
OLD_HTTPS_PUBLISH_DIR = os.path.join(OLD_ROOT_PUBLISH_DIR, 'https', 'repos')

NEW_DISTRIBUTOR_CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % YUM_DISTRIBUTOR_ID
NEW_DISTRIBUTOR_CONF = read_json_config(NEW_DISTRIBUTOR_CONF_FILE_PATH)


def migrate(*args, **kwargs):
    """
    For each repository with a yum distributor, clean up the old yum distributor's
    mess and re-publish the repository with the new distributor.
    """
    if not api._is_initialized():
        api.initialize()

    distributor_collection = get_collection('repo_distributors')
    yum_distributors = list(
        distributor_collection.find({'distributor_type_id': YUM_DISTRIBUTOR_ID}))

    repo_ids = list(set(d['repo_id'] for d in yum_distributors))
    repo_objs = model.Repository.objects(repo_id__in=repo_ids)
    repos = dict((repo_obj.repo_id, repo_obj.to_transfer_repo()) for repo_obj in repo_objs)

    for d in yum_distributors:
        repo = repos[d['repo_id']]
        config = d['config'] or {}

        if d['last_publish'] is None:
            continue

        _clear_working_dir(repo)
        _clear_old_publish_dirs(repo, config)
        _re_publish_repository(repo, d)

    _remove_legacy_publish_dirs()


def _clear_working_dir(repo, working_dir=None):
    """
    Clear out the repository's distributor's working directory
    """

    working_dir = working_dir or REPO_WORKING_DIR % repo['id']

    if os.path.exists(working_dir):

        for i in os.listdir(working_dir):

            p = os.path.join(working_dir, i)

            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)

            else:
                try:
                    os.unlink(p)
                # this is a best-effort kinda thing
                except:
                    pass


def _clear_old_publish_dirs(repo, config):
    """
    Remove the repository's old http and https publish directories (if they exist),
    including any parent directories that may fall empty as a result.
    """

    relative_publish_dir = config.get('relative_url', repo['id']) or repo['id']

    if relative_publish_dir.startswith('/'):
        relative_publish_dir = relative_publish_dir[1:]

    http_publish_dir = config.get('http_publish_dir', OLD_HTTP_PUBLISH_DIR)
    repo_http_publish_dir = os.path.join(http_publish_dir, relative_publish_dir)

    if os.path.exists(repo_http_publish_dir):
        shutil.rmtree(repo_http_publish_dir, ignore_errors=True)
        _clear_orphaned_publish_dirs(http_publish_dir, os.path.dirname(repo_http_publish_dir))

    https_publish_dir = config.get('https_publish_dir', OLD_HTTPS_PUBLISH_DIR)
    repo_https_publish_dir = os.path.join(https_publish_dir, relative_publish_dir)

    if os.path.exists(repo_https_publish_dir):
        shutil.rmtree(repo_https_publish_dir, ignore_errors=True)
        _clear_orphaned_publish_dirs(https_publish_dir, os.path.dirname(repo_https_publish_dir))


def _clear_orphaned_publish_dirs(root_dir, publish_dir):
    """
    Clear out empty parent directories underneath a root publish directory.
    """

    if not publish_dir.startswith(root_dir):
        return

    if root_dir.endswith('/'):
        root_dir = root_dir[:-1]

    if publish_dir.endswith('/'):
        publish_dir = publish_dir[:-1]

    if publish_dir == root_dir:
        return

    if not os.path.exists(publish_dir):
        return

    contents = os.listdir(publish_dir)

    if contents == ['listing'] or not contents:

        listing_path = os.path.join(publish_dir, 'listing')

        if os.path.exists(listing_path):
            try:
                os.unlink(listing_path)
            except:
                pass

        if os.path.islink(publish_dir):
            try:
                os.unlink(publish_dir)
            except:
                pass

        else:
            os.rmdir(publish_dir)

    _clear_orphaned_publish_dirs(root_dir, os.path.dirname(publish_dir))


def _re_publish_repository(repo_obj, distributor):
    """
    Re-publish the repository using the new yum distributor.

    NOTE: this may be a bit time-consuming.
    """

    repo = repo_obj.to_transfer_repo()
    repo.working_dir = distributor_working_dir(distributor['distributor_type_id'],
                                               repo.id)
    conduit = RepoPublishConduit(repo.id, distributor['id'])
    config = PluginCallConfiguration(NEW_DISTRIBUTOR_CONF, distributor['config'])

    publisher = Publisher(repo, conduit, config, YUM_DISTRIBUTOR_ID)
    publisher.process_lifecycle()


def _remove_legacy_publish_dirs():
    _clear_orphaned_publish_dirs(OLD_ROOT_PUBLISH_DIR, OLD_HTTP_PUBLISH_DIR)
    _clear_orphaned_publish_dirs(OLD_ROOT_PUBLISH_DIR, OLD_HTTPS_PUBLISH_DIR)


def distributor_working_dir(distributor_type_id, repo_id, mkdir=True):
    """
    Determines the working directory for a distributor to use for a repository.
    If the mkdir argument is set to true, the directory will be created as
    part of this call. See the module-level docstrings for more information on
    the directory structure.
    :param mkdir: if true, this call will create the directory; otherwise the
                  full path will just be generated
    :type  mkdir: bool
    :return: full path on disk to the directory the distributor can use for the
             given repository
    :rtype:  str
    """
    storage_dir = pulp_config.config.get('server', 'storage_dir')
    working_dir = os.path.join(storage_dir, 'working', 'repos', repo_id, 'distributors',
                               distributor_type_id)

    if mkdir and not os.path.exists(working_dir):
        os.makedirs(working_dir)

    return working_dir
