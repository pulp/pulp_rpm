# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from pulp.server.db.connection import get_collection


def migrate(*args, **kwargs):
    """
    Migrate existing ISOImporters to use the new configuration key names.
    """
    repo_importers = get_collection('repo_importers')
    # This query changes the names of some of the importer keys to be the new names
    rename_query = {'$rename': {
        'config.feed_url': 'config.feed',
        'config.num_threads': 'config.max_downloads',
        # proxy_url was technically just a hostname in the past. it was a badly named parameter.
        'config.proxy_url': 'config.proxy_host',
        'config.proxy_user': 'config.proxy_username',
        'config.remove_missing_units': 'config.remove_missing',
        'config.validate_units': 'config.validate',
    }}
    repo_importers.update({'importer_type_id': 'iso_importer'}, rename_query, safe=True, multi=True)