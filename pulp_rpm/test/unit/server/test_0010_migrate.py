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

from pulp.server.db.connection import get_collection
from pulp.server.db.migrate.models import _import_all_the_way

import rpm_support_base


class YumImporterConfigMigrationTests(rpm_support_base.PulpRPMTests):
    def setUp(self):
        rpm_support_base.PulpRPMTests.setUp(self)

        self.repo_importers = get_collection('repo_importers')

        importers = (

            # Proxy changes
            {'repo_id' : 'proxy',
             'id' : 'yum_importer',
             'importer_type_id' : 'yum_importer',
             'config' : {
                'proxy_url' : 'localhost',
                'proxy_port' : 3128,
                'proxy_user' : 'user-1',
                'proxy_password' : 'pass-1',
             },
            },

            # Non-proxy changes + unchanged things
            {'repo_id' : 'mixed',
             'id' : 'yum_importer',
             'importer_type_id' : 'yum_importer',
             'config' : {
                'feed_url' : 'http://localhost/repo',
                'ssl_verify' : True,
                'num_threads' : 42,
                'verify_checksum' : True,
                'remove_old' : False,
                'num_old_packages' : 3,
                'skip' : ['rpm'],
                'max_speed' : 1024,
              },
             },

            # Things to remove + unchanged things
            {'repo_id' : 'remove',
             'id' : 'yum_importer',
             'importer_type_id' : 'yum_importer',
             'config' : {
                 'feed' : 'localhost',
                 'newest' : True,
                 'verify_size' : True,
                 'purge_orphaned' : True,
             },
            },

            # Non-yum importer
            {'repo_id' : 'no-touch',
             'id' : 'non_yum_importer',
             'importer_type_id' : 'non_yum_importer',
             'config' : {
                 'feed' : 'localhost',
                 'newest' : True,
                 'verify_size' : True,
                 'purge_orphaned' : True,
             },
            },
        )

        for importer in importers:
            self.repo_importers.save(importer, safe=True)

    def tearDown(self):
        super(YumImporterConfigMigrationTests, self).tearDown()
        self.repo_importers.remove()

    def test_migrate(self):
        # Test
        migration = _import_all_the_way('pulp_rpm.migrations.0010_yum_importer_config_keys')
        migration.migrate()

        # Verify
        proxy = self.repo_importers.find_one({'repo_id' : 'proxy'})
        self.assertTrue('proxy_url' not in proxy['config'])
        self.assertTrue('proxy_user' not in proxy['config'])
        self.assertTrue('proxy_pass' not in proxy['config'])
        self.assertEqual(proxy['config']['proxy_host'], 'localhost')
        self.assertEqual(proxy['config']['proxy_username'], 'user-1')
        self.assertEqual(proxy['config']['proxy_password'], 'pass-1')

        mixed = self.repo_importers.find_one({'repo_id' : 'mixed'})
        self.assertTrue('feed_url' not in mixed['config'])
        self.assertTrue('ssl_verify' not in mixed['config'])
        self.assertTrue('num_threads' not in mixed['config'])
        self.assertTrue('verify_checksum' not in mixed['config'])
        self.assertTrue('remove_old' not in mixed['config'])
        self.assertTrue('num_old_packages' not in mixed['config'])
        self.assertEqual(mixed['config']['feed'], 'http://localhost/repo')
        self.assertEqual(mixed['config']['ssl_validation'], True)
        self.assertEqual(mixed['config']['max_downloads'], 42)
        self.assertEqual(mixed['config']['validate'], True)
        self.assertEqual(mixed['config']['remove_missing'], False)
        self.assertEqual(mixed['config']['retain_old_count'], 3)
        self.assertEqual(mixed['config']['skip'], ['rpm'])
        self.assertEqual(mixed['config']['max_speed'], 1024)

        remove = self.repo_importers.find_one({'repo_id' : 'remove'})
        self.assertTrue('newest' not in remove['config'])
        self.assertTrue('verify_size' not in remove['config'])
        self.assertTrue('purge_orphaned' not in remove['config'])
        self.assertEqual(remove['config']['feed'], 'localhost')

        no_touch = self.repo_importers.find_one({'repo_id' : 'no-touch'})
        self.assertEqual(no_touch['config']['feed'], 'localhost')
        self.assertEqual(no_touch['config']['newest'], True)
        self.assertEqual(no_touch['config']['verify_size'], True)
        self.assertEqual(no_touch['config']['purge_orphaned'], True)
