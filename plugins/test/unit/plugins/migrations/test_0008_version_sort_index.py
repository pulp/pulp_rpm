# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from pulp.plugins.types import database as types_db
from pulp.server.db.migrate.models import _import_all_the_way

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM)
from pulp_rpm.common import version_utils
from pulp_rpm.devel import rpm_support_base


class VersionSortIndexMigrationTests(rpm_support_base.PulpRPMTests):

    def tearDown(self):
        super(VersionSortIndexMigrationTests, self).tearDown()

        for type_id in (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM):
            collection = types_db.type_units_collection(type_id)
            collection.remove()

    def test_migrate(self):
        # Setup
        for type_id in (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM):
            self.add_sample_data(type_id)

        # Test
        migration = _import_all_the_way('pulp_rpm.plugins.migrations.0008_version_sort_index')
        migration.migrate()

        # Verify

        # The migration should cover these three types, so make sure they were all included
        for type_id in (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM):
            collection = types_db.type_units_collection(type_id)

            test_me = collection.find_one({'version' : '1.1'})
            self.assertEqual(test_me['version_sort_index'], version_utils.encode('1.1'))
            self.assertEqual(test_me['release_sort_index'], version_utils.encode('1.1'))

            # Make sure the script didn't run on units that already have the indexes
            test_me = collection.find_one({'version' : '3.1'})
            self.assertEqual(test_me['version_sort_index'], 'fake')
            self.assertEqual(test_me['release_sort_index'], 'fake')

    def add_sample_data(self, type_id):
        collection = types_db.type_units_collection(type_id)

        collection.save({'version' : '1.1', 'release' : '1.1'}, safe=True)
        collection.save({'version' : '3.1', 'version_sort_index' : 'fake',
                         'release' : '3.1', 'release_sort_index' : 'fake'}, safe=True)
