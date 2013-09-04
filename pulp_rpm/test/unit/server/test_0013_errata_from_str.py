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

import json

from pulp.server.db.connection import get_collection
from pulp.server.db.migrate.models import _import_all_the_way

import rpm_support_base


class TestMigrateErrataFromStr(rpm_support_base.PulpRPMTests):
    """
    Test migration #0013.
    """
    def setUp(self):
        super(TestMigrateErrataFromStr, self).setUp()

        self.collection = get_collection('units_errata')

        errata = [
            json.loads(ERRATA_OLD),
            json.loads(ERRATA_NEW),
        ]

        for erratum in errata:
            self.collection.save(erratum, safe=True)

    def tearDown(self):
        super(TestMigrateErrataFromStr, self).tearDown()

        self.collection.remove(safe=True)

    def test_migrate(self):
        migration = _import_all_the_way('pulp_rpm.migrations.0013_errata_from_str')

        # Run the migration
        migration.migrate()

        # Verify that this one's "from_str" got changed to "from"
        old = self.collection.find_one({'id': 'RHEA-2012:0003'})
        self.assertEqual(old.get('from', None), 'errata@redhat.com')
        self.assertFalse('from_str' in old)

        # Verify that this one's "from" is still "from"
        new = self.collection.find_one({'id': 'RHEA-2012:0004'})
        self.assertEqual(new.get('from', None), 'errata@redhat.com')
        self.assertFalse('from_str' in new)


ERRATA_OLD = """{
	"status" : "stable",
	"updated" : "",
	"description" : "Bird_Erratum",
	"issued" : "2012-01-27 16:08:08",
	"pushcount" : 1,
	"references" : [ ],
	"_content_type_id" : "erratum",
	"id" : "RHEA-2012:0003",
	"from_str" : "errata@redhat.com",
	"_storage_path" : null,
	"reboot_suggested" : false,
	"severity" : "",
	"rights" : "",
	"_ns" : "units_erratum",
	"title" : "Bird_Erratum",
	"solution" : "",
	"summary" : "",
	"version" : "1",
	"release" : "1",
	"type" : "security",
	"pkglist" : [
		{
			"packages" : [
				{
					"src" : "http://www.fedoraproject.org",
					"name" : "crow",
					"filename" : "crow-0.8-1.noarch.rpm",
					"epoch" : null,
					"version" : "0.8",
					"release" : "1",
					"arch" : "noarch"
				},
				{
					"src" : "http://www.fedoraproject.org",
					"name" : "stork",
					"filename" : "stork-0.12-2.noarch.rpm",
					"epoch" : null,
					"version" : "0.12",
					"release" : "2",
					"arch" : "noarch"
				},
				{
					"src" : "http://www.fedoraproject.org",
					"name" : "duck",
					"filename" : "duck-0.6-1.noarch.rpm",
					"epoch" : null,
					"version" : "0.6",
					"release" : "1",
					"arch" : "noarch"
				}
			],
			"name" : "1",
			"short" : ""
		}
	]
}"""


ERRATA_NEW = """{
	"status" : "stable",
	"updated" : "",
	"description" : "Fish_Erratum",
	"issued" : "2012-01-27 16:08:18",
	"pushcount" : 1,
	"references" : [ ],
	"_content_type_id" : "erratum",
	"id" : "RHEA-2012:0004",
	"from" : "errata@redhat.com",
	"_storage_path" : null,
	"reboot_suggested" : false,
	"severity" : "",
	"rights" : "",
	"_ns" : "units_erratum",
	"title" : "Fish_Erratum",
	"solution" : "",
	"summary" : "",
	"version" : "1",
	"release" : "1",
	"type" : "security",
	"pkglist" : [
		{
			"packages" : [
				{
					"src" : "http://www.fedoraproject.org",
					"name" : "crow",
					"filename" : "crow-0.8-2.noarch.rpm",
					"epoch" : null,
					"version" : "0.8",
					"release" : "1",
					"arch" : "noarch"
				},
				{
					"src" : "http://www.fedoraproject.org",
					"name" : "stork",
					"filename" : "stork-0.12-3.noarch.rpm",
					"epoch" : null,
					"version" : "0.12",
					"release" : "2",
					"arch" : "noarch"
				},
				{
					"src" : "http://www.fedoraproject.org",
					"name" : "duck",
					"filename" : "duck-0.6-2.noarch.rpm",
					"epoch" : null,
					"version" : "0.6",
					"release" : "1",
					"arch" : "noarch"
				}
			],
			"name" : "1",
			"short" : ""
		}
	]
}"""

