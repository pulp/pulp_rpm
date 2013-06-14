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
from nectar.config import DownloaderConfig
from pulp.plugins.conduits.repo_sync import RepoSyncConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository
import pulp.server.managers.factory as manager_factory

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd import metadata
from pulp_rpm.plugins.importers.yum.sync import RepoSync

manager_factory.initialize()


class TestImportUnknown(unittest.TestCase):
    def setUp(self):
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org', '/foo/bar', DownloaderConfig())
        self.repo = Repository('repo1')
        self.conduit = RepoSyncConduit(self.repo.id, 'yum_importer', 'user', 'me')
        self.config = PluginCallConfiguration({}, {})
        self.reposync = RepoSync(self.repo, self.conduit, self.config)

    def test_known_type(self):
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.metadata_files.metadata = {'primary': mock.MagicMock()}

        self.reposync.import_unknown_metadata_files(self.metadata_files)

        # nothing can be done without calling init_unit, so this is a good
        # indicator that the file type was skipped.
        self.assertEqual(self.conduit.init_unit.call_count, 0)

    @mock.patch('shutil.copyfile')
    def test_unknown_type(self, mock_copyfile):
        file_info = {
            'checksum': {'hex_digest':'foo', 'algorithm':'bar'},
            'local_path': '/a/b/c.xml'
        }

        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        self.metadata_files.metadata = {'myspecialdata': file_info}

        self.reposync.import_unknown_metadata_files(self.metadata_files)

        self.conduit.init_unit.assert_called_once_with(
            models.YumMetadataFile.TYPE,
            {'repo_id': self.repo.id, 'data_type': 'myspecialdata'},
            {'checksum': 'foo', 'checksum_type': 'bar'},
            self.repo.id + '/c.xml'
        )
        unit = self.conduit.init_unit.return_value

        self.conduit.save_unit.assert_called_once_with(unit)

        mock_copyfile.assert_called_once_with(file_info['local_path'], unit.storage_path)
