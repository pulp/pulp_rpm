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

from bson import BSON
import glob
import os.path

import mock
from rpmUtils import transaction
from pulp.server.db.migrate.models import MigrationModule

import rpm_support_base


class TestMigrationAddMetadata(rpm_support_base.PulpRPMTests):
    def setUp(self):
        super(TestMigrationAddMetadata, self).setUp()
        self.module = MigrationModule('pulp_rpm.migrations.0005_rpm_changelog_files')._module

        self.fake_unit = {'_storage_path': '/tmp/foo'}
        self.mock_ts = mock.MagicMock()
        self.mock_collection = mock.MagicMock()

        self.mock_package = mock.MagicMock()
        self.mock_package.changelog = [('now', 'foo@bar.com', 'description'),]
        self.mock_package.filelist = ['/a', '/b', '/c']
        self.mock_package.files = {
            'ghost': ['/xyz'],
            'dir': ['/foo', '/bar'],
            'file': ['/a', '/b', '/c'],
        }

    def verify_saved_unit(self, saved_unit):
        self.assertTrue('files' in saved_unit)
        for key, value in saved_unit['files'].iteritems():
            for item in value:
                self.assertTrue(isinstance(item, unicode))

        self.assertTrue('filelist' in saved_unit)
        for value in saved_unit['filelist']:
            self.assertTrue(isinstance(value, unicode))

        self.assertTrue('changelog' in saved_unit)
        for entry in saved_unit['changelog']:
            # don't inspect timestamp, which is the first item
            for item in entry[1:]:
                self.assertTrue(isinstance(item, unicode))
        # this is how mongo will encode it, so make sure this is possible
        BSON.encode(saved_unit)

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('createrepo.yumbased.CreateRepoPackage')
    def test_migrate_filelist(self, mock_package_class, mock_exists):
        mock_package_class.return_value = self.mock_package

        self.module._migrate_unit(self.fake_unit, self.mock_ts, self.mock_collection)

        self.assertEqual(self.mock_collection.save.call_count, 1)
        saved_unit = self.mock_collection.save.call_args[0][0]
        self.verify_saved_unit(saved_unit)
        self.assertEqual(saved_unit['files'], self.mock_package.files)
        self.assertEqual(saved_unit['filelist'], self.mock_package.filelist)
        self.assertEqual(
            saved_unit['changelog'][0],
            self.module._decode_changelog(self.mock_package.changelog[0])
        )

    def test_with_real_packages(self):
        current_dir = os.path.dirname(__file__)
        paths = glob.glob(os.path.join(
            current_dir,
            '../../data/repos.fedorapeople.org/repos/pulp/pulp/demo_repos/zoo/*.rpm'
        ))
        ts = transaction.initReadOnlyTransaction()

        for path in paths:
            fake_unit = {'_storage_path': path}
            self.module._migrate_unit(fake_unit, ts, self.mock_collection)
            saved_unit = self.mock_collection.save.call_args[0][0]
            self.verify_saved_unit(saved_unit)

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('createrepo.yumbased.CreateRepoPackage')
    def test_latin1_metadata(self, mock_package_class, mock_exists):
        # the following string cannot be decoded as utf8, so this checks that the
        # migration handles latin1 decoding also. Mongo will barf if we hand it
        # this string.
        self.mock_package.filelist.append('/usr/share/doc/man-pages-da-0.1.1/l\xe6smig')
        mock_package_class.return_value = self.mock_package
        self.module._migrate_unit(self.fake_unit, self.mock_ts, self.mock_collection)

        saved_unit = self.mock_collection.save.call_args[0][0]
        self.verify_saved_unit(saved_unit)
