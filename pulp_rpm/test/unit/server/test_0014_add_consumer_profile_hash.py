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

from pulp.server.db.connection import get_collection
from pulp.server.db.migrate.models import _import_all_the_way
from pulp.server.db.model.consumer import UnitProfile

from pulp_rpm.plugins.profilers import yum
import rpm_support_base


class TestMigration(rpm_support_base.PulpRPMTests):
    def setUp(self):
        self.collection = get_collection('consumer_unit_profiles')

    def tearDown(self):
        self.collection.drop()

    def test_migration(self):
        """
        Assert that the migration adds the appropriate hashes to the three consumers.
        """
        consumer_unit_profiles = [
            {'consumer_id': 'consumer_1', 'content_type': 'rpm',
             'profile': [{'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '1.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package B', 'epoch': 0, 'version': '2.0.3', 'release': '3.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package C', 'epoch': 0, 'version': '1.3.6', 'release': '2.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'}]},
            {'consumer_id': 'consumer_2', 'content_type': 'rpm',
             'profile': [{'name': 'Package B', 'epoch': 0, 'version': '2.0.3', 'release': '3.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '1.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package C', 'epoch': 0, 'version': '1.3.6', 'release': '2.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'}]},
            {'consumer_id': 'consumer_3', 'content_type': 'rpm',
             'profile': [{'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '1.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package B', 'epoch': 0, 'version': '2.0.3', 'release': '3.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package C', 'epoch': 0, 'version': '1.3.6', 'release': '2.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package D', 'epoch': 1, 'version': '12.1.6', 'release': '27.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'}]},
            {'consumer_id': 'consumer_3',
             'content_type': 'some_other_type_that_should_be_left_alone',
             'profile': [{'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '1.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package B', 'epoch': 0, 'version': '2.0.3', 'release': '3.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
                         {'name': 'Package C', 'epoch': 0, 'version': '1.3.6', 'release': '2.el6',
                          'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'}]},
        ]
        self.collection.insert(consumer_unit_profiles)
        migration_module = _import_all_the_way('pulp_rpm.migrations.0014_add_consumer_profile_hash')

        # Run the migration
        migration_module.migrate('arg_1', kwarg_1='kwarg_1')

        # Get the profiles
        consumer_1_profile = self.collection.find_one({'consumer_id': 'consumer_1'})
        consumer_2_profile = self.collection.find_one({'consumer_id': 'consumer_2'})
        consumer_3_rpm_profile = self.collection.find_one({'consumer_id': 'consumer_3',
                                                           'content_type': 'rpm'})
        consumer_3_other_profile = self.collection.find_one(
            {'consumer_id': 'consumer_3',
             'content_type': 'some_other_type_that_should_be_left_alone'})

        # Consumer 1 and Consumer 2 should have the same hashes, even though the RPMs were recorded
        # in a different order
        self.assertEqual(consumer_1_profile['profile_hash'], consumer_2_profile['profile_hash'])
        # Consumer 3 should have a different hash, since it has an additional package
        self.assertNotEqual(consumer_1_profile['profile_hash'],
                            consumer_3_rpm_profile['profile_hash'])

        # Consumer 3's non-RPM profile should not have a hash
        self.assertTrue('profile_hash' not in consumer_3_other_profile)

        # Now, let's make sure the hashes are actually correct. We only have to check 1 and 3, since
        # we already asserted that 1 is equal to 2
        profiler = yum.YumProfiler()
        for profile in [consumer_1_profile, consumer_3_rpm_profile]:
            sorted_profile = profiler.update_profile(None, profile['profile'], None, None)
            expected_hash = UnitProfile.calculate_hash(profile['profile'])
            self.assertEqual(profile['profile_hash'], expected_hash)
