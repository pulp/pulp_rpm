# -*- coding: utf-8 -*-
#
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

import shutil
import unittest
import os

import mock

from pulp.server.exceptions import PulpDataException
from pulp.plugins.model import Repository
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.export_distributor.distributor import ISODistributor, entry_point
from pulp_rpm.yum_plugin import util
from pulp_rpm.common.ids import (TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_ERRATA, TYPE_ID_DRPM,
                                 TYPE_ID_SRPM, TYPE_ID_RPM, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_DISTRIBUTOR_EXPORT)
from pulp_rpm.common.constants import (PUBLISH_HTTPS_KEYWORD, PUBLISH_HTTP_KEYWORD,
                                       EXPORT_HTTPS_DIR, EXPORT_DIRECTORY_KEYWORD, EXPORT_HTTP_DIR)


class TestEntryPoint(unittest.TestCase):

    def test_entry_point(self):
        distributor, config = entry_point()
        self.assertEquals(distributor, ISODistributor)


class TestISODistributor(unittest.TestCase):

    def test_metadata(self):
        """
        Test the overridden metadata method in ISODistributor
        """
        metadata = ISODistributor.metadata()
        expected_types = [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                          TYPE_ID_DISTRO, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]
        self.assertEquals(metadata['id'], TYPE_ID_DISTRIBUTOR_EXPORT)
        self.assertEqual(set(expected_types), set(metadata['types']))

    def test_validate_config(self):
        """
        Test the validate_config method in ISODistributor, which just hands the config off to a
        helper method in export_utils
        """
        # Setup
        validate_config = export_utils.validate_export_config
        export_utils.validate_export_config = mock.MagicMock()
        distributor = ISODistributor()

        # Test. All validate_config should do is hand the config argument to the export_utils
        # validator
        distributor.validate_config(None, 'config', None)
        export_utils.validate_export_config.assert_called_once_with('config')

        # Clean up
        export_utils.validate_export_config = validate_config

    @mock.patch('pulp_rpm.yum_plugin.metadata.cancel_createrepo', autospec=True)
    def test_cancel_publish_repo(self, mock_cancel_createrepo):
        """
        Test cancel_publish_repo, which is not currently fully supported
        """
        distributor = ISODistributor()
        distributor.working_dir = '/working/dir'

        distributor.cancel_publish_repo()

        mock_cancel_createrepo.assert_called_once_with(distributor.working_dir)

    def test_set_progress(self):
        """
        Test set_progress, which simply checks if the progress_callback is None before calling it
        """
        # Setup
        mock_callback = mock.Mock()
        distributor = ISODistributor()

        # Test
        distributor.set_progress('id', 'status', mock_callback)
        mock_callback.assert_called_once_with('id', 'status')

    def test_set_progress_no_callback(self):
        """
        Assert that set_progress don't not attempt to call the callback when it is None
        """
        # Setup
        distributor = ISODistributor()

        # Test
        try:
            distributor.set_progress('id', 'status', None)
        except AttributeError:
            self.fail('set_progress should not try to call None')


class TestPublishRepo(unittest.TestCase):
    """
    Tests publish_repo in ISODistributor
    """
    def setUp(self):
        self.config_dict = {
            PUBLISH_HTTP_KEYWORD: False,
            PUBLISH_HTTPS_KEYWORD: True
        }

        # Set up the distributor
        self.distributor = ISODistributor()
        self.distributor._publish_isos = mock.Mock(spec=ISODistributor._publish_isos)

        # Arguments for the distributor
        self.repo = Repository(id='repo-id', working_dir='/working/dir')
        self.mock_conduit = mock.Mock(spec=RepoPublishConduit)
        self.config = PluginCallConfiguration({}, self.config_dict)

        # It's difficult to mock patch the export_utils, so do it here.
        self.cleanup_working_dir = export_utils.cleanup_working_dir
        self.validate_export_config = export_utils.validate_export_config
        self.export_complete_repo = export_utils.export_complete_repo
        self.export_incremental = export_utils.export_incremental_content
        self.retrieve_repo_config = export_utils.retrieve_repo_config
        self.generate_listing_files = util.generate_listing_files
        self.rmtree = shutil.rmtree
        self.makdirs = os.makedirs

        export_utils.cleanup_working_dir = mock.Mock(spec=export_utils.cleanup_working_dir)
        export_utils.validate_export_config = mock.Mock(return_value=(True, None))
        export_utils.export_complete_repo = mock.Mock(return_value=({}, {'errors': []}))
        export_utils.export_incremental_content = mock.Mock(return_value=({}, {'errors': ()}))
        export_utils.retrieve_repo_config = mock.Mock(return_value=('/working/dir/repo', None))
        util.generate_listing_files = mock.Mock()
        shutil.rmtree = mock.Mock(spec=shutil.rmtree)
        os.makedirs = mock.Mock(spec=os.makedirs)

    def tearDown(self):
        export_utils.cleanup_working_dir = self.cleanup_working_dir
        export_utils.validate_export_config = self.validate_export_config
        export_utils.export_complete_repo = self.export_complete_repo
        export_utils.export_incremental_content = self.export_incremental
        export_utils.retrieve_repo_config = self.retrieve_repo_config
        util.generate_listing_files = self.generate_listing_files
        shutil.rmtree = self.rmtree
        os.makedirs = self.makdirs

    def test_failed_override_config(self):
        """
        Tests that when invalid override configuration is given, an exception is raised.
        """
        # Setup
        export_utils.validate_export_config.return_value = (False, 'failed validation')

        # Test
        self.assertRaises(PulpDataException, self.distributor.publish_repo, self.repo,
                          self.mock_conduit, self.config)

    def test_working_dir_cleanup(self):
        """
        Check that the working directory is cleaned before use. This is done because the ISOs are
        currently stored there
        """
        self.distributor.publish_repo(self.repo, self.mock_conduit, self.config)
        shutil.rmtree.assert_called_once_with(self.repo.working_dir, ignore_errors=True)
        os.makedirs.assert_called_once_with(self.repo.working_dir)

    def test_export_with_export_dir(self):
        """
        Test that _publish_isos isn't called when there is an export directory in the config, and that
        the correct working directory is used.
        """
        # Set the config to have an export directory
        self.config_dict[EXPORT_DIRECTORY_KEYWORD] = '/my/export/dir'
        config = PluginCallConfiguration({}, self.config_dict)

        # Test
        self.distributor.publish_repo(self.repo, self.mock_conduit, config)
        self.assertEqual(0, self.distributor._publish_isos.call_count)
        self.assertEqual(1, self.mock_conduit.build_success_report.call_count)

    def test_export_iso_publish(self):
        """
        Test that _publish_iso gets called when an export dir isn't in the config
        """
        self.distributor.publish_repo(self.repo, self.mock_conduit, self.config)
        self.assertEqual(1, self.distributor._publish_isos.call_count)
        self.assertEqual(self.repo, self.distributor._publish_isos.call_args[0][0])
        self.assertEqual(self.config, self.distributor._publish_isos.call_args[0][1])
        self.assertEqual(1, self.mock_conduit.build_success_report.call_count)

    def test_export_complete_repo(self):
        """
        Test that when a date filter doesn't exist, export_complete_repo is called
        """
        self.distributor.publish_repo(self.repo, self.mock_conduit, self.config)
        self.assertEqual(1, export_utils.export_complete_repo.call_count)
        self.assertEqual('repo-id', export_utils.export_complete_repo.call_args[0][0])
        self.assertEqual('/working/dir/repo', export_utils.export_complete_repo.call_args[0][1])
        self.assertEqual(self.config, export_utils.export_complete_repo.call_args[0][3])

    def test_export_listings_file(self):
        """
        Test that the listings file is created
        """
        self.distributor.publish_repo(self.repo, self.mock_conduit, self.config)
        util.generate_listing_files.assert_called_once_with('/working/dir', '/working/dir/repo')

    def test_export_incremental(self):
        """
        Test that when a date filter is not None, export_incremental_content is called
        """
        # Setup
        export_utils.retrieve_repo_config.return_value = ('/working/dir', 'filter')

        # Test
        self.distributor.publish_repo(self.repo, self.mock_conduit, self.config)
        self.assertEqual(1, export_utils.export_incremental_content.call_count)
        self.assertEqual('/working/dir', export_utils.export_incremental_content.call_args[0][0])
        self.assertEqual('filter', export_utils.export_incremental_content.call_args[0][2])

    def test_failed_publish(self):
        """
        Confirm that when the details dict contains errors, a failure report is generated
        """
        # Setup
        self.distributor.details['errors'] = ['critical_error_thingy']
        export_utils.export_complete_repo.return_value = ({}, {'errors': ['thousands of them']})

        # Test
        self.distributor.publish_repo(self.repo, self.mock_conduit, self.config)
        self.assertEqual(1, self.mock_conduit.build_failure_report.call_count)


class TestPublishIsos(unittest.TestCase):
    """
    Tests the _publish_isos method in GroupISODistributor. This method decides what the publishing
    directories should be, cleans them up, and hands everything off to the publish_iso method in
    export_utils.
    """
    def setUp(self):
        self.distributor = ISODistributor()
        self.repo = Repository('repo_id', working_dir='/working/dir')
        self.config = {PUBLISH_HTTP_KEYWORD: True, PUBLISH_HTTPS_KEYWORD: True}

        self.publish_iso = export_utils.publish_isos
        export_utils.publish_isos = mock.Mock()

    def tearDown(self):
        export_utils.publish_isos = self.publish_iso

    @mock.patch('shutil.rmtree', autospec=True)
    def test_publish_isos(self, mock_rmtree):
        """
        Test that publish_isos is called with the expected arguments
        """
        # Setup
        http_publish_dir = os.path.join(EXPORT_HTTP_DIR, self.repo.id)
        https_publish_dir = os.path.join(EXPORT_HTTPS_DIR, self.repo.id)

        # Test
        self.distributor._publish_isos(self.repo, PluginCallConfiguration({}, self.config))
        self.assertEqual(2, mock_rmtree.call_count)
        self.assertEqual(http_publish_dir, mock_rmtree.call_args_list[0][0][0])
        self.assertEqual(https_publish_dir, mock_rmtree.call_args_list[1][0][0])
        export_utils.publish_isos.assert_called_once_with(self.repo.working_dir, self.repo.id,
                                                          http_publish_dir, https_publish_dir, None,
                                                          None)

    @mock.patch('shutil.rmtree', autospec=True)
    def test_publish_http_https_false(self, mock_rmtree):
        """
        Test that when the config has publishing http and https set to false, publish_isos is called
        with None for https_dir and http_dir
        """
        # Setup
        self.config[PUBLISH_HTTPS_KEYWORD] = False
        self.config[PUBLISH_HTTP_KEYWORD] = False
        self.distributor._publish_isos(self.repo, PluginCallConfiguration({}, self.config))
        http_publish_dir = os.path.join(EXPORT_HTTP_DIR, self.repo.id)
        https_publish_dir = os.path.join(EXPORT_HTTPS_DIR, self.repo.id)

        # Test
        self.assertEqual(2, mock_rmtree.call_count)
        self.assertEqual(http_publish_dir, mock_rmtree.call_args_list[0][0][0])
        self.assertEqual(https_publish_dir, mock_rmtree.call_args_list[1][0][0])
        export_utils.publish_isos.assert_called_once_with(self.repo.working_dir, self.repo.id, None,
                                                          None, None, None)
