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
We had a v1 --> v2 upgrade bug[0] where the units_package_group collection's
conditional_package_names attribute remained in the v1 format, rather than being migrated by the v1
migration script to the v2 format. This migration performs that transformation.

[0] https://bugzilla.redhat.com/show_bug.cgi?id=986026
"""

from pulp.server.db.connection import get_collection, initialize


def migrate(*args, **kwargs):
    """
    Loop over all the documents in the units_package_group collection, inspecting the
    conditional_package_names attribute. If that attribute is a dictionary, this method will
    convert the dictionary into a list of lists, where the first item in each list represents the
    keys from the dictionary, and the second item represents the values.
    """
    package_group_collection = get_collection('units_package_group')
    for package_group in package_group_collection.find():
        if isinstance(package_group['conditional_package_names'], dict):
            new_conditional_package_names = [[key, value] \
                for key, value in package_group['conditional_package_names'].items()]
            package_group_collection.update(
                {'_id': package_group['_id']},
                {'$set': {'conditional_package_names': new_conditional_package_names}}, safe=True)


# Allow this migration to be run outside of the migration system
if __name__ == "__main__":
    initialize()
    migrate()
