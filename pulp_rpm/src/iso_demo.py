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

from pulp_rpm.common import ids

from pulp.common import pic
from okaara.prompt import Prompt, COLOR_LIGHT_PURPLE, COLOR_LIGHT_BLUE

ISO_FEED = 'http://pkilambi.fedorapeople.org/test_file_repo/'
DISTRIBUTOR_ID = 'iso_dist'

# -- ui -----------------------------------------------------------------------

def pause(p):
    p.prompt('Press enter to continue...', allow_empty=True)

def divider(p):
    p.write('==============================')

def title(p, text):
    p.write(text, color=COLOR_LIGHT_PURPLE)

# -- functional ---------------------------------------------------------------

def delete_repo(repo_id):
    url = '/v2/repositories/%s/' % repo_id
    try:
        pic.GET(url)
    except pic.RequestError:
        return
    pic.DELETE(url)

def create_repo(repo_id):
    body = {'id' : repo_id}
    pic.POST('/v2/repositories/', body=body)

def add_iso_importer(repo_id, queries):
    importer_config = {
        'feed_url': ISO_FEED,
        'queries': queries,
    }

    body = {
        'importer_type_id' : ids.TYPE_ID_IMPORTER_ISO,
        'importer_config' : importer_config,
    }

    pic.POST('/v2/repositories/%s/importers/' % repo_id, body=body)

def add_iso_distributor(repo_id):
    distributor_config = {
        'serve_http': True,
        'serve_https': True,
    }

    body = {
        'distributor_type_id' : ids.TYPE_ID_DISTRIBUTOR_ISO,
        'distributor_config' : distributor_config,
        'distributor_id' : DISTRIBUTOR_ID,
    }

    pic.POST('/v2/repositories/%s/distributors/' % repo_id, body=body)

def sync(repo_id):
    pic.POST('/v2/repositories/%s/actions/sync/' % repo_id)

def list_units(prompt, repo_id):
    criteria = {'type_ids' : [ids.TYPE_ID_ISO]}
    body = {'criteria' : criteria}

    status, body = pic.POST('/v2/repositories/%s/search/units/' % repo_id, body=body)

    units = [u['metadata'] for u in body]
    for u in units:
        msg = '  Name: %-15s Version: %-15s Author: %-15s' % (u['name'], u['version'], u['author'])
        prompt.write(msg)

def publish(repo_id):
    body = {'id' : DISTRIBUTOR_ID}
    pic.POST('/v2/repositories/%s/actions/publish/' % repo_id, body=body)

# -- script -------------------------------------------------------------------

def main():
    p = Prompt()
    pic.connect()
    pic.LOG_BODIES = False

    repo_ids = ['one', 'two', 'author', 'httpd']

    title(p, 'Creating & Configuring Repositories')
    p.write('  Repository: one    Queries: thias/php')
    p.write('  Repository: two    Queries: thias/php, larstobi/dns')
    p.write('  Repository: author Queries: thias')
    p.write('  Repository: httpd  Queries: httpd')

    for r in repo_ids:
        delete_repo(r)
        create_repo(r)

    add_iso_importer('one', ['thias/php'])
    add_iso_importer('two', ['thias/php', 'larstobi/dns'])
    add_iso_importer('author', ['thias'])
    add_iso_importer('httpd', ['httpd'])

    add_iso_distributor('one')
    add_iso_distributor('two')
    add_iso_distributor('author')
    add_iso_distributor('httpd')

    pause(p)
    p.write('')

    title(p, 'Synchronizing Repositories')

    sync('one')
    sync('two')
    sync('author')
    sync('httpd')

    pause(p)
    p.write('')

    title(p, 'Publishing Repositories')

    publish('one')
    publish('two')
    publish('author')
    publish('httpd')

    pause(p)
    p.write('')

    title(p, 'Displaying Repository Contents')

    p.write('Repository: one', color=COLOR_LIGHT_BLUE)
    list_units(p, 'one')
    p.write('')
    p.write('Repository: two', color=COLOR_LIGHT_BLUE)
    list_units(p, 'two')
    p.write('')
    p.write('Repository: author', color=COLOR_LIGHT_BLUE)
    list_units(p, 'author')
    p.write('')
    p.write('Repository: httpd', color=COLOR_LIGHT_BLUE)
    list_units(p, 'httpd')

if __name__ == '__main__':
    main()
