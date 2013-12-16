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

import os
import shutil

from pulp.server.db.model.repository import Repo, RepoDistributor
from pulp.server.managers.repo.publish import RepoPublishManager


YUM_DISTRIBUTOR_ID = 'yum_distributor'

REPO_WORKING_DIRECTORY = '/var/lib/pulp/working/%s/distributors/' + YUM_DISTRIBUTOR_ID

OLD_ROOT_PUBLISH_DIR = '/var/lib/pulp/published'
OLD_HTTP_PUBLISH_DIR = os.path.join(OLD_ROOT_PUBLISH_DIR, 'http', 'repos')
OLD_HTTPS_PUBLISH_DIR = os.path.join(OLD_ROOT_PUBLISH_DIR, 'https', 'repos')


def migrate(*args, **kwargs):

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

    working_dir = REPO_WORKING_DIRECTORY % repo['id']

    if os.path.exists(working_dir):

        for i in os.listdir(working_dir):

            p = os.path.join(working_dir, i)

            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)

            else:
                try:
                    os.unlink(p)
                except:
                    # this is a best-effort kinda thing
                    pass


def _clear_old_publish_dirs(repo, config):

    relative_publish_dir = config.get('relative_url', repo.id) or repo.id

    if relative_publish_dir.startswith('/'):
        relative_publish_dir = relative_publish_dir[1:]

    http_publish_dir = config.get('http_publish_dir', OLD_HTTP_PUBLISH_DIR)
    repo_http_publish_dir = os.path.join(http_publish_dir, relative_publish_dir)

    if os.path.exists(repo_http_publish_dir):
        shutil.rmtree(repo_http_publish_dir, ignore_errors=True)

    https_publish_dir = config.get('https_publish_dir', OLD_HTTPS_PUBLISH_DIR)
    repo_https_publish_dir = os.path.join(https_publish_dir, relative_publish_dir)

    if os.path.exists(repo_https_publish_dir):
        shutil.rmtree(repo_https_publish_dir, ignore_errors=True)


def _re_publish_repository(repo, distributor):

    manager = RepoPublishManager()
    manager.publish(repo['id'], distributor['id'])


