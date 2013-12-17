# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

"""
The new distributor now stores the master copy of a published repository outside
of the distributor's working directory. It also stores the published repositories
in a new location.

This script cleans up all of the aforementioned directories and re-publishes the
corresponding repositories.
"""

import os
import shutil

from pulp.server.db.model.repository import Repo, RepoDistributor
from pulp.server.managers.repo.publish import RepoPublishManager


YUM_DISTRIBUTOR_ID = 'yum_distributor'

REPO_WORKING_DIR = '/var/lib/pulp/working/%s/distributors/' + YUM_DISTRIBUTOR_ID

OLD_ROOT_PUBLISH_DIR = '/var/lib/pulp/published'
OLD_HTTP_PUBLISH_DIR = os.path.join(OLD_ROOT_PUBLISH_DIR, 'http', 'repos')
OLD_HTTPS_PUBLISH_DIR = os.path.join(OLD_ROOT_PUBLISH_DIR, 'https', 'repos')


def migrate(*args, **kwargs):
    """
    For each repository with a yum distributor, clean up the old yum distributor's
    mess and re-publish the repository with the new distributor.
    """

    distributor_collection = RepoDistributor.get_collection()
    yum_distributors = list(distributor_collection.find({'distributor_type_id': YUM_DISTRIBUTOR_ID}))

    repo_collection = Repo.get_collection()
    repo_ids = list(set(d['repo_id'] for d in yum_distributors))
    repos = dict((r['id'], r) for r in repo_collection.find({'id': {'$in': repo_ids}}))

    for d in yum_distributors:
        repo = repos[d['repo_id']]
        config = d['config'] or {}

        if d['last_publish'] is None:
            continue

        _clear_working_dir(repo)
        _clear_old_publish_dirs(repo, config)
        _re_publish_repository(repo, d)


def _clear_working_dir(repo):
    """
    Clear out the repository's distributor's working directory
    """

    working_dir = REPO_WORKING_DIR % repo['id']

    if os.path.exists(working_dir):

        for i in os.listdir(working_dir):

            p = os.path.join(working_dir, i)

            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)

            else:
                try: os.unlink(p)
                # this is a best-effort kinda thing
                except: pass


def _clear_old_publish_dirs(repo, config):
    """
    Remove the repository's old http and https publish directories (if they exist),
    including any parent directories that may fall empty as a result.
    """

    relative_publish_dir = config.get('relative_url', repo.id) or repo.id

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
            try: os.unlink(listing_path)
            except: pass

        os.rmdir(publish_dir)

    _clear_orphaned_publish_dirs(root_dir, os.path.dirname(publish_dir))


def _re_publish_repository(repo, distributor):
    """
    Re-publish the repository using the new yum distributor.

    NOTE: this may be a bit time-consuming.
    """

    manager = RepoPublishManager()
    manager.publish(repo['id'], distributor['id'])


