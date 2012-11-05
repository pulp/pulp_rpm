# Copyright (c) 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os
import mock
import sys

from pulp.client.commands import options
from pulp.client.commands.unit import UnitCopyCommand

from pulp_rpm.common import ids
from pulp_rpm.extension.admin import copy
import rpm_support_base


class CopyRpmCommandTests(rpm_support_base.PulpClientTests):

    FROM_REPO_ID = 'test-repo-src'
    TO_REPO_ID = 'test-repo-dst'
    TYPE_IDS = [ids.TYPE_ID_RPM]
    RECURSIVE = True

    def setUp(self):
        super(CopyRpmCommandTests, self).setUp()
        self.command = copy.RpmCopyCommand(self.context)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitCopyCommand))

        # Ensure the correct metadata
        self.assertEqual(self.command.name, 'rpm')
        self.assertEqual(self.command.description, copy.DESC_RPM)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.copy')
    def test_copy(self, mock_binding):
        # Setup
        
        data = {
            'from-repo-id' : self.FROM_REPO_ID,
            'to-repo-id' : self.TO_REPO_ID,
            'recursive' : self.RECURSIVE,
        }

        # Test
        copy._copy(self.context, ids.TYPE_ID_RPM, **data)

        # Verify
        passed = dict([('type_ids', self.TYPE_IDS), 
                 ('to-repo-id', self.TO_REPO_ID), 
                 ('from-repo-id', self.FROM_REPO_ID),
                 ('recursive', self.RECURSIVE)])

        mock_binding.assert_called_with(self.FROM_REPO_ID, self.TO_REPO_ID, **passed)


class CopyErrataCommandTests(rpm_support_base.PulpClientTests):

    FROM_REPO_ID = 'test-repo-src'
    TO_REPO_ID = 'test-repo-dst'
    TYPE_IDS = [ids.TYPE_ID_ERRATA]
    RECURSIVE = True

    def setUp(self):
        super(CopyErrataCommandTests, self).setUp()
        self.command = copy.ErrataCopyCommand(self.context)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitCopyCommand))

        # Ensure the correct metadata
        self.assertEqual(self.command.name, 'errata')
        self.assertEqual(self.command.description, copy.DESC_ERRATA)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.copy')
    def test_copy(self, mock_binding):
        # Setup
        
        data = {
            'from-repo-id' : self.FROM_REPO_ID,
            'to-repo-id' : self.TO_REPO_ID,
            'recursive' : self.RECURSIVE,
        }

        # Test
        copy._copy(self.context, ids.TYPE_ID_ERRATA, **data)

        # Verify
        passed = dict([('type_ids', self.TYPE_IDS), 
                 ('to-repo-id', self.TO_REPO_ID), 
                 ('from-repo-id', self.FROM_REPO_ID),
                 ('recursive', self.RECURSIVE)])

        mock_binding.assert_called_with(self.FROM_REPO_ID, self.TO_REPO_ID, **passed)


class CopyPackageGrpCommandTests(rpm_support_base.PulpClientTests):

    FROM_REPO_ID = 'test-repo-src'
    TO_REPO_ID = 'test-repo-dst'
    TYPE_IDS = [ids.TYPE_ID_PKG_GROUP]
    RECURSIVE = True

    def setUp(self):
        super(CopyPackageGrpCommandTests, self).setUp()
        self.command = copy.PackageGroupCopyCommand(self.context)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitCopyCommand))

        # Ensure the correct metadata
        self.assertEqual(self.command.name, 'group')
        self.assertEqual(self.command.description, copy.DESC_PKG_GROUP)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.copy')
    def test_copy(self, mock_binding):
        # Setup
        
        data = {
            'from-repo-id' : self.FROM_REPO_ID,
            'to-repo-id' : self.TO_REPO_ID,
            'recursive' : self.RECURSIVE,
        }

        # Test
        copy._copy(self.context, ids.TYPE_ID_PKG_GROUP, **data)

        # Verify
        passed = dict([('type_ids', self.TYPE_IDS), 
                 ('to-repo-id', self.TO_REPO_ID), 
                 ('from-repo-id', self.FROM_REPO_ID),
                 ('recursive', self.RECURSIVE)])

        mock_binding.assert_called_with(self.FROM_REPO_ID, self.TO_REPO_ID, **passed)


class CopyPackageCategoryCommandTests(rpm_support_base.PulpClientTests):

    FROM_REPO_ID = 'test-repo-src'
    TO_REPO_ID = 'test-repo-dst'
    TYPE_IDS = [ids.TYPE_ID_PKG_CATEGORY]
    RECURSIVE = True

    def setUp(self):
        super(CopyPackageCategoryCommandTests, self).setUp()
        self.command = copy.PackageCategoryCopyCommand(self.context)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitCopyCommand))

        # Ensure the correct metadata
        self.assertEqual(self.command.name, 'category')
        self.assertEqual(self.command.description, copy.DESC_PKG_CATEGORY)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.copy')
    def test_copy(self, mock_binding):
        # Setup
        
        data = {
            'from-repo-id' : self.FROM_REPO_ID,
            'to-repo-id' : self.TO_REPO_ID,
            'recursive' : self.RECURSIVE,
        }

        # Test
        copy._copy(self.context, ids.TYPE_ID_PKG_CATEGORY, **data)

        # Verify
        passed = dict([('type_ids', self.TYPE_IDS), 
                 ('to-repo-id', self.TO_REPO_ID), 
                 ('from-repo-id', self.FROM_REPO_ID),
                 ('recursive', self.RECURSIVE)])

        mock_binding.assert_called_with(self.FROM_REPO_ID, self.TO_REPO_ID, **passed)
        

class CopyDistributionCommandTests(rpm_support_base.PulpClientTests):

    FROM_REPO_ID = 'test-repo-src'
    TO_REPO_ID = 'test-repo-dst'
    TYPE_IDS = [ids.TYPE_ID_DISTRO]
    RECURSIVE = True

    def setUp(self):
        super(CopyDistributionCommandTests, self).setUp()
        self.command = copy.DistributionCopyCommand(self.context)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UnitCopyCommand))

        # Ensure the correct metadata
        self.assertEqual(self.command.name, 'distribution')
        self.assertEqual(self.command.description, copy.DESC_DISTRIBUTION)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.copy')
    def test_copy(self, mock_binding):
        # Setup
        
        data = {
            'from-repo-id' : self.FROM_REPO_ID,
            'to-repo-id' : self.TO_REPO_ID,
            'recursive' : self.RECURSIVE,
        }

        # Test
        copy._copy(self.context, ids.TYPE_ID_DISTRO, **data)

        # Verify
        passed = dict([('type_ids', self.TYPE_IDS), 
                 ('to-repo-id', self.TO_REPO_ID), 
                 ('from-repo-id', self.FROM_REPO_ID),
                 ('recursive', self.RECURSIVE)])

        mock_binding.assert_called_with(self.FROM_REPO_ID, self.TO_REPO_ID, **passed)
        
