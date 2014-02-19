#!/usr/bin/python
#
# Copyright (c) 2012 Red Hat, Inc.
#
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import shutil
import unittest
import os

import mock
from pulp.server.exceptions import PulpDataException
from pulp.plugins.model import RepositoryGroup
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_publish import RepoGroupPublishConduit

from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.export_distributor.groupdistributor import GroupISODistributor, \
    entry_point
from pulp_rpm.common.ids import (TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_ERRATA, TYPE_ID_DRPM,
                                 TYPE_ID_SRPM, TYPE_ID_RPM, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_DISTRIBUTOR_GROUP_EXPORT)
from pulp_rpm.common.constants import (PUBLISH_HTTPS_KEYWORD, PUBLISH_HTTP_KEYWORD,
                                       EXPORT_DIRECTORY_KEYWORD, GROUP_EXPORT_HTTP_DIR,
                                       GROUP_EXPORT_HTTPS_DIR)


class TestEntryPoint(unittest.TestCase):

    def test_entry_point(self):
        distributor, config = entry_point()
        self.assertEquals(distributor, GroupISODistributor)


class TestGroupISODistributor(unittest.TestCase):
    """
    Tests the metadata and validate_config methods for GroupISODistributor
    """
    def test_metadata(self):
        metadata = GroupISODistributor.metadata()
        expected_types = [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                          TYPE_ID_DISTRO, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]
        self.assertEquals(metadata['id'], TYPE_ID_DISTRIBUTOR_GROUP_EXPORT)
        self.assertEqual(set(expected_types), set(metadata['types']))

    def test_validate_config(self):
        # Setup
        validate_config = export_utils.validate_export_config
        export_utils.validate_export_config = mock.MagicMock()
        distributor = GroupISODistributor()

        # All validate_config should do is hand the config argument to the export_utils validator
        distributor.validate_config(None, 'config', None)
        export_utils.validate_export_config.assert_called_once_with('config')

        # Clean up
        export_utils.validate_export_config = validate_config


class TestPublishGroup(unittest.TestCase):
    """
    Tests publish_group in GroupISODistributor
    """
    def setUp(self):
        """
        The distributor retrieves a lot of stuff from the database. It also creates and removes
        directories and files. This class does not test the functionality of the methods that handle
        any of that, so many are replaced with mocks here
        """
        self.group_distributor = GroupISODistributor()
        # Create arguments to be handed to the distributor
        self.config_dict = {
            PUBLISH_HTTP_KEYWORD: False,
            PUBLISH_HTTPS_KEYWORD: True
        }
        self.config = PluginCallConfiguration({}, self.config_dict)
        self.mock_conduit = mock.MagicMock(spec=RepoGroupPublishConduit)
        self.mock_conduit.distributor_id = 'mock_distributor_idq'
        self.repo_group = RepositoryGroup('test-group', '', '', {}, ['repo_id'], '/dir')

        # We aren't testing _publish_isos here, so let's not call it
        self.group_distributor._publish_isos = mock.MagicMock(
            spec=GroupISODistributor._publish_isos)

        self.patches = []
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'util.generate_listing_files')
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'export_utils.cleanup_working_dir')
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'export_utils.validate_export_config', return_value=(True, None))
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'export_utils.export_complete_repo', return_value=({}, {'errors': []}))
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'export_utils.export_incremental_content',
                             return_value=({}, {'errors': {}}))
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'export_utils.retrieve_group_export_config',
                             return_value=([('repo_id', '/dir')], None))
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'shutil.rmtree')
        self.patches.append(patcher)
        patcher = mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                             'os.makedirs')
        self.patches.append(patcher)

        for patch_handler in self.patches:
            patch_handler.start()

    def tearDown(self):
        for patch_handler in self.patches:
            patch_handler.stop()

    def test_failed_override_config(self):
        """
        Tests that when invalid override configuration is given, an exception is raised.
        """
        # Setup
        export_utils.validate_export_config.return_value = (False, 'failed validation')

        # Test
        self.assertRaises(PulpDataException, self.group_distributor.publish_group, self.repo_group,
                          self.mock_conduit, self.config)

    def test_clean_working_dir(self):
        """
        Check that the working directory is cleaned before use. This is done because the ISOs are
        currently stored there
        """
        self.group_distributor.publish_group(self.repo_group, self.mock_conduit, self.config)
        shutil.rmtree.assert_called_once_with(self.repo_group.working_dir, ignore_errors=True)
        os.makedirs.assert_called_once_with(self.repo_group.working_dir)

    def test_export_iso_publish(self):
        """
        Test exporting a repository to ISO images. This happens when there is no export directory
        """
        # Call publish_group
        self.group_distributor.publish_group(self.repo_group, self.mock_conduit, self.config)

        # Test that _publish_isos is called with the correct arguments
        self.assertEqual(1, self.group_distributor._publish_isos.call_count)
        self.assertEqual(self.repo_group, self.group_distributor._publish_isos.call_args[0][0])
        self.assertEqual(self.config, self.group_distributor._publish_isos.call_args[0][1])

    def test_export_complete_repo_call(self):
        """
        Test that the export_complete_repo method is called with the correct arguments
        """
        self.group_distributor.publish_group(self.repo_group, self.mock_conduit, self.config)
        self.assertEqual(1, export_utils.export_complete_repo.call_count)
        self.assertEqual('repo_id', export_utils.export_complete_repo.call_args[0][0])
        self.assertEqual('/dir', export_utils.export_complete_repo.call_args[0][1])
        self.assertEqual(self.config, export_utils.export_complete_repo.call_args[0][3])

    def test_incremental_export_call(self):
        """
        Test the the export_incremental_content method is called with the correct arguments
        """
        # Setup retrieve_group_export_config return value to return a date filter
        export_utils.retrieve_group_export_config.return_value = ([('repo_id', '/dir')], 'filter')

        # Test that export_incremental_content was called correctly
        self.group_distributor.publish_group(self.repo_group, self.mock_conduit, self.config)
        self.assertEqual(1, export_utils.export_incremental_content.call_count)
        self.assertEqual('/dir', export_utils.export_incremental_content.call_args[0][0])
        self.assertEqual('filter', export_utils.export_incremental_content.call_args[0][2])

    def test_export_dir(self):
        """
        Test that when an export directory is in the config, ISOs are not created
        """
        # Setup
        self.config_dict[EXPORT_DIRECTORY_KEYWORD] = '/export/dir'
        config = PluginCallConfiguration({}, self.config_dict)

        # Test that _publish_isos is not called
        self.group_distributor.publish_group(self.repo_group, self.mock_conduit, config)
        self.assertEqual(0, self.group_distributor._publish_isos.call_count)

    def test_failed_publish(self):
        """
        Test that when errors are reported, a failure report is generated
        """
        # Setup. Insert an error in the details
        export_utils.export_complete_repo.return_value = ({}, {'errors': ['error_list']})

        # Test
        self.group_distributor.publish_group(self.repo_group, self.mock_conduit, self.config)
        self.mock_conduit.build_failure_report.assert_called_once_with(self.group_distributor.summary,
                                                                       self.group_distributor.details)


class TestPublishIsos(unittest.TestCase):
    """
    Tests the _publish_isos helper method in GroupISODistributor. This really just decides the correct
    http(s) publishing directories, cleans them up, and calls export_utils.publish_isos.
    """
    def setUp(self):
        self.distributor = GroupISODistributor()
        self.repo_group = RepositoryGroup('group_id', '', '', {}, [], '/working/dir')
        self.config = {PUBLISH_HTTP_KEYWORD: True, PUBLISH_HTTPS_KEYWORD: True}

        self.publish_iso = export_utils.publish_isos
        export_utils.publish_isos = mock.Mock()

    def tearDown(self):
        export_utils.publish_isos = self.publish_iso

    @mock.patch('shutil.rmtree', autospec=True)
    def test_publish_isos(self, mock_rmtree):
        # Setup. These are the expected http and https publishing directories
        http_publish_dir = os.path.join(GROUP_EXPORT_HTTP_DIR, self.repo_group.id)
        https_publish_dir = os.path.join(GROUP_EXPORT_HTTPS_DIR, self.repo_group.id)

        # Test
        self.distributor._publish_isos(self.repo_group, PluginCallConfiguration({}, self.config))
        self.assertEqual(2, mock_rmtree.call_count)
        self.assertEqual(http_publish_dir, mock_rmtree.call_args_list[0][0][0])
        self.assertEqual(https_publish_dir, mock_rmtree.call_args_list[1][0][0])
        export_utils.publish_isos.assert_called_once_with(self.repo_group.working_dir,
                                                          self.repo_group.id, http_publish_dir,
                                                          https_publish_dir, None, None)

    @mock.patch('shutil.rmtree', autospec=True)
    def test_publish_http_https_false(self, mock_rmtree):
        # Setup
        self.config[PUBLISH_HTTPS_KEYWORD] = False
        self.config[PUBLISH_HTTP_KEYWORD] = False
        self.distributor._publish_isos(self.repo_group, PluginCallConfiguration({}, self.config))
        http_publish_dir = os.path.join(GROUP_EXPORT_HTTP_DIR, self.repo_group.id)
        https_publish_dir = os.path.join(GROUP_EXPORT_HTTPS_DIR, self.repo_group.id)

        # Test that publish_isos was called with None for the http and https directories.
        export_utils.publish_isos.assert_called_once_with(self.repo_group.working_dir,
                                                          self.repo_group.id, None, None, None, None)
        self.assertEqual(2, mock_rmtree.call_count)
        self.assertEqual(http_publish_dir, mock_rmtree.call_args_list[0][0][0])
        self.assertEqual(https_publish_dir, mock_rmtree.call_args_list[1][0][0])
