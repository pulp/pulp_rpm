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

import unittest

import mock
from pulp.plugins.conduits.upload import UploadConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, SyncReport

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import upload


class TestUploadGroup(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')
        self.conduit = UploadConduit(self.repo.id, 'yum_importer', 'user', 'me')
        self.metadata = {'unit_metadata': {
            'mandatory_package_names': None,
            'name': 'pulp-test',
            'default': None,
            'display_order': 0,
            'description': 'test group',
            'user_visible': None,
            'translated_name': '',
            'translated_description': {},
            'optional_package_names': None,
            'default_package_names': None,
            'langonly': None,
            'conditional_package_names': []}
        }

    def test_upload(self):
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        unit_key = {'id': 'group1', 'repo_id': self.repo.id}

        report = upload.upload(self.repo, models.PackageGroup.TYPE, unit_key,
                               self.metadata, '', self.conduit,
                               PluginCallConfiguration({}, {}))

        self.conduit.init_unit.assert_called_once_with(models.PackageGroup.TYPE,
                                                       unit_key, self.metadata, '')
        self.conduit.save_unit.assert_called_once_with(self.conduit.init_unit.return_value)
        self.assertTrue(isinstance(report, SyncReport))
        self.assertTrue(report.success_flag)
