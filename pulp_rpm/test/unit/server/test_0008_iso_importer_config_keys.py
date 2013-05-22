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

import rpm_support_base


class ISOImporterConfigKeysMigrationTests(rpm_support_base.PulpRPMTests):
    """
    Test migration #0008.
    """
    def setUp(self):
        super(self.__class__, self).setUp()
        self.repo_importers = get_collection('repo_importers')

        importers = (
            {"repo_id": "proxy",
             "importer_type_id": "iso_importer", "last_sync": "2013-04-09T16:57:06-04:00",
             "scheduled_syncs": [], "scratchpad": None,
             "config": {
                "proxy_user": "rbarlow",
                "feed_url": "http://pkilambi.fedorapeople.org/test_file_repo/",
                "proxy_url": "localhost", "proxy_password": "password", "proxy_port": 3128,
                "id": "proxy" },
             "id": "iso_importer"},
            # This one has only the configs that were changed set
            {'repo_id': 'test', 'importer_type_id': 'iso_importer',
             'config': {
                'feed_url': 'http://feed.com/isos', 'num_threads': 42,
                'proxy_url': 'proxy.com', 'proxy_user': 'jeeves',
                'remove_missing_units': False, 'validate_units': True},
             'id': 'iso_importer'},
            # This is here just to make sure we ignore it with our query, since this
            # migration should only alter ISOImporters
            {'repo_id': 'a_yum_repo', 'importer_type_id': 'yum_importer',
             'config': {'feed_url': 'This should not change.'}},
        )

        for importer in importers:
            self.repo_importers.save(importer, safe=True)

    def tearDown(self):
        super(self.__class__, self).tearDown()

        self.repo_importers.remove(safe=True)

    def test_migrate(self):
        migration = _import_all_the_way('pulp_rpm.migrations.0008_iso_importer_config_keys')

        # Run the migration
        migration.migrate()

        # Verify the proxy repo
        proxy = self.repo_importers.find_one({'repo_id': 'proxy'})
        self.assertEqual(proxy['importer_type_id'], 'iso_importer')
        self.assertEqual(proxy['last_sync'], '2013-04-09T16:57:06-04:00')
        self.assertEqual(proxy['scheduled_syncs'], [])
        self.assertEqual(proxy['scratchpad'], None)
        self.assertEqual(dict(proxy['config']), {
            u'proxy_username': u'rbarlow',
            u'feed': u'http://pkilambi.fedorapeople.org/test_file_repo/',
            u'proxy_host': u'localhost', u'proxy_password': u'password',
            u'proxy_port': 3128, u'id': u'proxy'})
        self.assertEqual(proxy['id'], 'iso_importer')

        # Verify the test repo
        test = self.repo_importers.find_one({'repo_id': 'test'})
        self.assertEqual(test['importer_type_id'], 'iso_importer')
        self.assertEqual(dict(test['config']), {
            u'max_downloads': 42,
            u'feed': u'http://feed.com/isos',
            u'proxy_host': u'proxy.com', u'proxy_username': u'jeeves',
            u'remove_missing': False, u'validate': True})
        self.assertEqual(test['id'], 'iso_importer')

        # verify that the yum repo wasn't touched
        a_yum_repo = self.repo_importers.find_one({'repo_id': 'a_yum_repo'})
        self.assertEqual(a_yum_repo['importer_type_id'], 'yum_importer')
        self.assertEqual(dict(a_yum_repo['config']),
                         {u'feed_url': u'This should not change.'})