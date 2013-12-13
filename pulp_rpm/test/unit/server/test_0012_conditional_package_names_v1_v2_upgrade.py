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
from pulp.server.db.migrate.models import _import_all_the_way

from pulp_rpm.devel import rpm_support_base


class ConditionalPackageNamesUpgradeTests(rpm_support_base.PulpRPMTests):
    def setUp(self):
        super(ConditionalPackageNamesUpgradeTests, self).setUp()
        self.package_group_collection = get_collection('units_package_group')

    def tearDown(self):
        super(ConditionalPackageNamesUpgradeTests, self).tearDown()
        self.package_group_collection.drop()

    def test_migrate(self):
        # Let's set up some package groups, some with the new way, and some with the old way
        # We'll only put the name and conditional_package_names attributes since the
        # migration only touches those fields
        package_groups = [
            {"name": "v1_style_1", "conditional_package_names" : {'a': 1, 'b': 2}},
            {"name": "v1_style_2", "conditional_package_names" : {'b': 1, 'c': 3}},
            {"name": "v2_style", "conditional_package_names" : [['d', 4], ['e', 5]]}]
        for package_group in package_groups:
            self.package_group_collection.insert(package_group)
        migration = _import_all_the_way(
            'pulp_rpm.migrations.0012_conditional_package_names_v1_v2_upgrade')

        # Run the migration
        migration.migrate()

        # Inspect the package groups
        expected_package_groups = [
            {"name": "v1_style_1", "conditional_package_names" : [['a', 1], ['b', 2]]},
            {"name": "v1_style_2", "conditional_package_names" : [['b', 1], ['c', 3]]},
            {"name": "v2_style", "conditional_package_names" : [['d', 4], ['e', 5]]}]
        for expected_package_group in expected_package_groups:
            package_group = self.package_group_collection.find_one(
                {'name': expected_package_group['name']})
            self.assertTrue(isinstance(package_group['conditional_package_names'], list))
            self.assertEqual(len(package_group['conditional_package_names']),
                             len(expected_package_group['conditional_package_names']))
            # Since dictionaries don't have ordering, we cannot assert that the expected
            # list is the same as the actual list. Instead, we assert that the lengths are
            # the same, and that all the expected items appear in the actual
            for pair in expected_package_group['conditional_package_names']:
                self.assertTrue(pair in package_group['conditional_package_names'])