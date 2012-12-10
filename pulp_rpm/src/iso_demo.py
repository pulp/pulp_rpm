# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
import sys

from pulp_rpm.common import constants, ids

from pulp.common import pic
from okaara.prompt import Prompt, COLOR_LIGHT_PURPLE, COLOR_LIGHT_BLUE

DISTRIBUTOR_ID = 'iso_dist'

# -- ui -----------------------------------------------------------------------

def pause(p):
    p.prompt('Press enter to continue...', allow_empty=True)

def divider(p):
    p.write('==============================')

def title(p, text):
    p.write(text, color=COLOR_LIGHT_PURPLE)

# -- functional ---------------------------------------------------------------

def delete_repo(repo):
    url = '/v2/repositories/%s/' % repo['id']
    try:
        pic.GET(url)
    except pic.RequestError:
        return
    pic.DELETE(url)

def create_repo(repo):
    body = {'id' : repo['id']}
    pic.POST('/v2/repositories/', body=body)

def add_iso_importer(repo):
    importer_config = {
        constants.CONFIG_FEED_URL: repo['feed'],
    }

    body = {
        'importer_type_id' : ids.TYPE_ID_IMPORTER_ISO,
        'importer_config' : importer_config,
    }

    pic.POST('/v2/repositories/%s/importers/' % repo['id'], body=body)

def add_iso_distributor(repo):
    distributor_config = {
        constants.CONFIG_SERVE_HTTP: True,
        constants.CONFIG_SERVE_HTTPS: True,
    }

    body = {
        'distributor_type_id' : ids.TYPE_ID_DISTRIBUTOR_ISO,
        'distributor_config' : distributor_config,
        'distributor_id' : DISTRIBUTOR_ID,
    }

    pic.POST('/v2/repositories/%s/distributors/' % repo['id'], body=body)

def sync(repo):
    pic.POST('/v2/repositories/%s/actions/sync/'%repo['id'])

def list_units(prompt, repo):
    criteria = {'type_ids' : [ids.TYPE_ID_ISO]}
    body = {'criteria' : criteria}

    status, body = pic.POST('/v2/repositories/%s/search/units/'%repo['id'], body=body)

    units = [u['metadata'] for u in body]
    for u in units:
        msg = '  Name: %-15s Size: %-15s Checksum: %-15s' % (u['name'], u['size'], u['checksum'])
        prompt.write(msg)


def publish(repo):
    body = {'id' : DISTRIBUTOR_ID}
    pic.POST('/v2/repositories/%s/actions/publish/'%repo['id'], body=body)


def main():
    p = Prompt()
    pic.connect()
    pic.LOG_BODIES = False

    repos = [{'id': 'test', 'feed': 'http://pkilambi.fedorapeople.org/test_file_repo/'},
             {'id': 'cdn',
                'feed': 'https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/iso'},]

    if not '--skip-delete' in sys.argv:
        title(p, 'Creating & Configuring Repositories')

        for r in repos:
            p.write('  Repository: %s'%r['id'])
            delete_repo(r)
            create_repo(r)
            add_iso_importer(r)
            add_iso_distributor(r)

        pause(p)
        p.write('')

    title(p, 'Synchronizing Repositories')

    for repo in repos:
        sync(repo)

    pause(p)
    p.write('')

    title(p, 'Publishing Repositories')

    for repo in repos:
        publish(repo)

    pause(p)
    p.write('')

    title(p, 'Displaying Repository Contents')

    for repo in repos:
        p.write('Repository: %s'%repo, color=COLOR_LIGHT_BLUE)
        list_units(p, repo)
        p.write('')

if __name__ == '__main__':
    main()
