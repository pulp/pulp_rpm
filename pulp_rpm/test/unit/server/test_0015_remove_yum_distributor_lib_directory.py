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

import unittest

import mock
from pulp.server.db.migrate.models import _import_all_the_way


class TestMigration(unittest.TestCase):

    @mock.patch('os.path.exists')
    @mock.patch('os.unlink')
    def test_migration(self, mock_unlink, mock_path_exists):
        """
        Assert that the migration removes the appropriate directory if it exists
        """
        migration_module = _import_all_the_way('pulp_rpm.migrations.0015_remove_yum_distributor_lib_directory')
        mock_path_exists.return_value = True
        # Run the migration
        migration_module.migrate()

        self.assertTrue(mock_unlink.called)
