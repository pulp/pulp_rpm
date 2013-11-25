#!/usr/bin/python
#
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

import mock
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from uuid import uuid4
from pymongo import cursor

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/distributors/")

from yum_distributor.distributor import YumDistributor, OLD_REL_PATH_KEYWORD
from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM, TYPE_ID_RPM, TYPE_ID_SRPM
from pulp_rpm.yum_plugin import util, metadata
from pulp.plugins.model import RelatedRepository, Repository, Unit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_config import RepoConfigConduit

from pulp.devel.mock_cursor import MockCursor

import distributor_mocks
import rpm_support_base
from mock import patch, ANY


class TestDistributor(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(TestDistributor, self).setUp()
        self.init()

    def tearDown(self):
        super(TestDistributor, self).tearDown()
        self.clean()

    def init(self):
        self.temp_dir = tempfile.mkdtemp()
        #pkg_dir is where we simulate units actually residing
        self.pkg_dir = os.path.join(self.temp_dir, "packages")
        os.makedirs(self.pkg_dir)
        #publish_dir simulates /var/lib/pulp/published
        self.http_publish_dir = os.path.join(self.temp_dir, "publish", "http")
        os.makedirs(self.http_publish_dir)

        self.https_publish_dir = os.path.join(self.temp_dir, "publish", "https")
        os.makedirs(self.https_publish_dir)

        self.repo_working_dir = os.path.join(self.temp_dir, "repo_working_dir")
        os.makedirs(self.repo_working_dir)
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data"))
        self.config_conduit = RepoConfigConduit(TYPE_ID_RPM)

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def get_units(self, count=5):
        units = []
        for index in range(0, count):
            u = self.get_unit()
            units.append(u)
        return units

    def get_unit(self, type_id="rpm"):
        uniq_id = uuid4()
        filename = "test_unit-%s" % (uniq_id)
        storage_path = os.path.join(self.pkg_dir, filename)
        metadata = {}
        metadata["relativepath"] = os.path.join("a/b/c", filename)
        metadata["filename"] = filename
        unit_key = uniq_id
        # Create empty file to represent the unit
        open(storage_path, "a+")
        u = Unit(type_id, unit_key, metadata, storage_path)
        return u

    def test_metadata(self):
        metadata = YumDistributor.metadata()
        self.assertEquals(metadata["id"], TYPE_ID_DISTRIBUTOR_YUM)
        self.assertTrue(TYPE_ID_RPM in metadata["types"])
        self.assertTrue(TYPE_ID_SRPM in metadata["types"])

    def test_validate_config(self):
        repo = mock.Mock(spec=Repository)
        repo.id = "testrepo"
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        # Confirm that required keys are successful
        req_kwargs = {}
        req_kwargs['http'] = True
        req_kwargs['https'] = False
        req_kwargs['relative_url'] = "sample_value"
        config = distributor_mocks.get_basic_config(**req_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertTrue(state)
        # Confirm required and optional are successful
        optional_kwargs = dict(req_kwargs)
        optional_kwargs['auth_ca'] = open(os.path.join(self.data_dir, "valid_ca.crt")).read()
        optional_kwargs['https_ca'] = open(os.path.join(self.data_dir, "valid_ca.crt")).read()
        optional_kwargs['protected'] = True
        optional_kwargs['checksum_type'] = "sha"
        optional_kwargs['skip'] = []
        optional_kwargs['auth_cert'] = open(os.path.join(self.data_dir, "cert.crt")).read()
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertTrue(state)
        # Test that config fails when a bad value for non_existing_dir is used
        optional_kwargs["http_publish_dir"] = "non_existing_dir"
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertFalse(state)
        # Test config succeeds with a good value of https_publish_dir
        optional_kwargs["http_publish_dir"] = self.temp_dir
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertTrue(state)
        del optional_kwargs["http_publish_dir"]
        # Test that config fails when a bad value for non_existing_dir is used
        optional_kwargs["https_publish_dir"] = "non_existing_dir"
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertFalse(state)
        # Test config succeeds with a good value of https_publish_dir
        optional_kwargs["https_publish_dir"] = self.temp_dir
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertTrue(state)
        del optional_kwargs["https_publish_dir"]

        # Confirm an extra key fails
        optional_kwargs["extra_arg_not_used"] = "sample_value"
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertFalse(state)
        self.assertTrue("extra_arg_not_used" in msg)

        # Confirm missing a required fails
        del optional_kwargs["extra_arg_not_used"]
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertTrue(state)

        del optional_kwargs["relative_url"]
        config = distributor_mocks.get_basic_config(**optional_kwargs)
        state, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertFalse(state)
        self.assertTrue("relative_url" in msg)

    def test_handle_symlinks(self):
        distributor = YumDistributor()
        units = []
        symlink_dir = os.path.join(self.temp_dir, "symlinks")
        num_links = 5
        for index in range(0,num_links):
            relpath = "file_%s.rpm" % (index)
            sp = os.path.join(self.pkg_dir, relpath)
            open(sp, "a") # Create an empty file
            if index % 2 == 0:
                # Ensure we can support symlinks in subdirs
                relpath = os.path.join("a", "b", "c", relpath)
            u = Unit("rpm", "unit_key_%s" % (index), {"relativepath":relpath}, sp)
            units.append(u)

        status, errors = distributor.handle_symlinks(units, symlink_dir)
        self.assertTrue(status)
        self.assertEqual(len(errors), 0)
        for u in units:
            symlink_path = os.path.join(symlink_dir, u.metadata["relativepath"])
            self.assertTrue(os.path.exists(symlink_path))
            self.assertTrue(os.path.islink(symlink_path))
            target = os.readlink(symlink_path)
            self.assertEqual(target, u.storage_path)
        # Test republish is successful
        status, errors = distributor.handle_symlinks(units, symlink_dir)
        self.assertTrue(status)
        self.assertEqual(len(errors), 0)
        for u in units:
            symlink_path = os.path.join(symlink_dir, u.metadata["relativepath"])
            self.assertTrue(os.path.exists(symlink_path))
            self.assertTrue(os.path.islink(symlink_path))
            target = os.readlink(symlink_path)
            self.assertEqual(target, u.storage_path)
        # Simulate a package is deleted
        os.unlink(units[0].storage_path)
        status, errors = distributor.handle_symlinks(units, symlink_dir)
        self.assertFalse(status)
        self.assertEqual(len(errors), 1)


    def test_get_relpath_from_unit(self):
        distributor = YumDistributor()
        test_unit = Unit("rpm", "unit_key", {}, "")

        test_unit.unit_key = {"fileName" : "test_1"}
        rel_path = util.get_relpath_from_unit(test_unit)
        self.assertEqual(rel_path, "test_1")

        test_unit.unit_key = {}
        test_unit.storage_path = "test_0"
        rel_path = util.get_relpath_from_unit(test_unit)
        self.assertEqual(rel_path, "test_0")

        test_unit.metadata["filename"] = "test_2"
        rel_path = util.get_relpath_from_unit(test_unit)
        self.assertEqual(rel_path, "test_2")

        test_unit.metadata["relativepath"] = "test_3"
        rel_path = util.get_relpath_from_unit(test_unit)
        self.assertEqual(rel_path, "test_3")

    def test_create_symlink(self):
        target_dir = os.path.join(self.temp_dir, "a", "b", "c", "d", "e")
        distributor = YumDistributor()
        # Create an empty file to serve as the source_path
        source_path = os.path.join(self.temp_dir, "some_test_file.txt")
        open(source_path, "a")
        symlink_path = os.path.join(self.temp_dir, "symlink_dir", "a", "b", "file_path.lnk")
        # Confirm subdir of symlink_path doesn't exist
        self.assertFalse(os.path.isdir(os.path.dirname(symlink_path)))
        self.assertTrue(util.create_symlink(source_path, symlink_path))
        # Confirm we created the subdir
        self.assertTrue(os.path.isdir(os.path.dirname(symlink_path)))
        self.assertTrue(os.path.exists(symlink_path))
        self.assertTrue(os.path.islink(symlink_path))
        # Verify the symlink points to the source_path
        a = os.readlink(symlink_path)
        self.assertEqual(a, source_path)

    def test_create_dirs(self):
        if os.geteuid() == 0:
            # skip if run as root
            return
        target_dir = os.path.join(self.temp_dir, "a", "b", "c", "d", "e")
        distributor = YumDistributor()
        self.assertFalse(os.path.exists(target_dir))
        self.assertTrue(util.create_dirs(target_dir))
        self.assertTrue(os.path.exists(target_dir))
        self.assertTrue(os.path.isdir(target_dir))
        # Test we can call it twice with no errors
        self.assertTrue(util.create_dirs(target_dir))
        # Remove permissions to directory and force an error
        orig_stat = os.stat(target_dir)
        try:
            os.chmod(target_dir, 0000)
            self.assertFalse(os.access(target_dir, os.R_OK))
            target_dir_b = os.path.join(target_dir, "f")
            self.assertFalse(util.create_dirs(target_dir_b))
        finally:
            os.chmod(target_dir, orig_stat.st_mode)

    @mock.patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_empty_publish(self, mock_factory):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_empty_publish"
        existing_units = []
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=existing_units, pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, http_publish_dir=self.http_publish_dir,
                http=True, https=True)
        distributor = YumDistributor()
        publish_conduit.repo_id = repo.id
        publish_conduit.distributor_id = 'foo'
        report = distributor.publish_repo(repo, publish_conduit, config)
        self.assertTrue(report.success_flag)
        summary = report.summary
        self.assertEqual(summary["num_package_units_attempted"], 0)
        self.assertEqual(summary["num_package_units_published"], 0)
        self.assertEqual(summary["num_package_units_errors"], 0)
        expected_repo_https_publish_dir = os.path.join(self.https_publish_dir, repo.id).rstrip('/')
        expected_repo_http_publish_dir = os.path.join(self.http_publish_dir, repo.id).rstrip('/')
        self.assertEqual(summary["https_publish_dir"], expected_repo_https_publish_dir)
        self.assertEqual(summary["http_publish_dir"], expected_repo_http_publish_dir)
        details = report.details
        self.assertEqual(len(details["errors"]), 0)

    @mock.patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_publish(self, mock_manager):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_publish"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_c/"
        existing_units = self.get_units(count=num_units)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm", existing_units=existing_units, pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, relative_url=relative_url,
                http=False, https=True)
        distributor = YumDistributor()
        publish_conduit.repo_id = repo.id
        publish_conduit.distributor_id = 'foo'
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        config_conduit = mock.Mock(spec=RepoConfigConduit)
        config_conduit.get_repo_distributors_by_relative_url.return_value = MockCursor([])


        status, msg = distributor.validate_config(repo, config, config_conduit)
        self.assertTrue(status)
        report = distributor.publish_repo(repo, publish_conduit, config)
        self.assertTrue(report.success_flag)
        summary = report.summary
        self.assertEqual(summary["num_package_units_attempted"], num_units)
        self.assertEqual(summary["num_package_units_published"], num_units)
        self.assertEqual(summary["num_package_units_errors"], 0)
        # Verify the listing files
        self.assertTrue(os.path.exists(os.path.join(self.https_publish_dir, 'listing')))
        self.assertFalse(os.path.exists(os.path.join(self.http_publish_dir, 'listing')))
        # Verify we did not attempt to publish to http
        expected_repo_http_publish_dir = os.path.join(self.http_publish_dir, relative_url)
        self.assertFalse(os.path.exists(expected_repo_http_publish_dir))

        expected_repo_https_publish_dir = os.path.join(self.https_publish_dir, relative_url).rstrip('/')
        self.assertEqual(summary["https_publish_dir"], expected_repo_https_publish_dir)
        self.assertTrue(os.path.exists(expected_repo_https_publish_dir))
        details = report.details
        self.assertEqual(len(details["errors"]), 0)
        #
        # Add a verification of the publish directory
        #
        self.assertTrue(os.path.exists(summary["https_publish_dir"]))
        self.assertTrue(os.path.islink(summary["https_publish_dir"].rstrip("/")))
        source_of_link = os.readlink(expected_repo_https_publish_dir.rstrip("/"))
        self.assertEquals(source_of_link, repo.working_dir)
        #
        # Verify the expected units
        #
        for u in existing_units:
            expected_link = os.path.join(expected_repo_https_publish_dir, u.metadata["relativepath"])
            self.assertTrue(os.path.exists(expected_link))
            actual_target = os.readlink(expected_link)
            expected_target = u.storage_path
            self.assertEqual(actual_target, expected_target)
        #
        # Now test flipping so https is disabled and http is enabled
        #
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir,
                http_publish_dir=self.http_publish_dir, relative_url=relative_url, http=True, https=False)
        report = distributor.publish_repo(repo, publish_conduit, config)
        self.assertTrue(report.success_flag)
        # Verify we did publish to http
        self.assertTrue(os.path.exists(expected_repo_http_publish_dir))

        # Verify we did not publish to https
        self.assertFalse(os.path.exists(expected_repo_https_publish_dir))

        # Verify we cleaned up the misc dirs under the https dir
        # NOTE there will be an empty listing file remaining
        self.assertEquals(len(os.listdir(self.https_publish_dir)), 1)


    @patch('pulp_rpm.yum_plugin.metadata.YumMetadataGenerator')
    def test_yum_plugin_generate_yum_metadata_checksum_from_config(self, mock_YumMetadataGenerator):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_publish"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_c/"
        existing_units = self.get_units(count=num_units)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm", existing_units=existing_units, pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, relative_url=relative_url,
                http=False, https=True, checksum_type='SHA')
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        config_conduit = mock.Mock(spec=RepoConfigConduit)
        config_conduit.get_repo_distributors_by_relative_url.return_value = MockCursor([])

        metadata.generate_yum_metadata(repo.id, repo.working_dir,publish_conduit, config)
        mock_YumMetadataGenerator.assert_called_with(ANY, checksum_type='SHA',
                                                     skip_metadata_types=ANY, is_cancelled=ANY,
                                                     group_xml_path=ANY,
                                                     updateinfo_xml_path=ANY,
                                                     custom_metadata_dict=ANY)

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    @patch('pulp_rpm.yum_plugin.metadata.YumMetadataGenerator')
    def test_yum_plugin_generate_yum_metadata_checksum_from_conduit(self,
                                                                    mock_YumMetadataGenerator,
                                                                    mock_distributor_manager):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_publish"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_c/"
        existing_units = self.get_units(count=num_units)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm",
                                                                existing_units=existing_units,
                                                                pkg_dir=self.pkg_dir)
        publish_conduit.repo_id = 'foo'
        publish_conduit.distributor_id = 'bar'
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, relative_url=relative_url,
                http=False, https=True)
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        config_conduit = mock.Mock(spec=RepoConfigConduit)
        config_conduit.get_repo_distributors_by_relative_url.return_value = MockCursor([])
        metadata.generate_yum_metadata(repo.id, repo.working_dir, publish_conduit, config,
                                        repo_scratchpad={'checksum_type': 'sha1'})
        mock_YumMetadataGenerator.assert_called_with(ANY, checksum_type='sha1',
                                                     skip_metadata_types=ANY, is_cancelled=ANY,
                                                     group_xml_path=ANY,
                                                     updateinfo_xml_path=ANY,
                                                     custom_metadata_dict=ANY)

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    @patch('pulp_rpm.yum_plugin.metadata.YumMetadataGenerator')
    def test_yum_plugin_generate_yum_metadata_checksum_from_conduit_sha1_conversion(self,
                                                                    mock_YumMetadataGenerator,
                                                                    mock_distributor_manager):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_publish"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_c/"
        existing_units = self.get_units(count=num_units)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm", existing_units=existing_units, pkg_dir=self.pkg_dir)
        publish_conduit.repo_id = 'foo'
        publish_conduit.distributor_id = TYPE_ID_DISTRIBUTOR_YUM
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, relative_url=relative_url,
                http=False, https=True)
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        config_conduit = mock.Mock(spec=RepoConfigConduit)
        config_conduit.get_repo_distributors_by_relative_url.return_value = MockCursor([])
        metadata.generate_yum_metadata(repo.id, repo.working_dir, publish_conduit, config,
                                        repo_scratchpad={'checksum_type': 'sha'})
        mock_YumMetadataGenerator.assert_called_with(ANY, checksum_type='sha1',
                                                     skip_metadata_types=ANY, is_cancelled=ANY,
                                                     group_xml_path=ANY,
                                                     updateinfo_xml_path=ANY,
                                                     custom_metadata_dict=ANY)
        mock_distributor_manager.return_value.update_distributor_config.\
            assert_called_with(ANY, ANY, {'checksum_type': 'sha1'})


    @patch('pulp.server.managers.factory.repo_distributor_manager')
    @patch('pulp_rpm.yum_plugin.metadata.YumMetadataGenerator')
    def test_yum_plugin_generate_yum_metadata_checksum_from_conduit_sha1_conversion_non_yum_distributor(self,
                                                                    mock_YumMetadataGenerator,
                                                                    mock_distributor_manager):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_publish"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_c/"
        existing_units = self.get_units(count=num_units)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm", existing_units=existing_units, pkg_dir=self.pkg_dir)
        publish_conduit.repo_id = 'foo'
        publish_conduit.distributor_id = 'foo'
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, relative_url=relative_url,
                http=False, https=True)
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        config_conduit = mock.Mock(spec=RepoConfigConduit)
        config_conduit.get_repo_distributors_by_relative_url.return_value = MockCursor([])
        metadata.generate_yum_metadata(repo.id, repo.working_dir, publish_conduit, config,
                                        repo_scratchpad={'checksum_type': 'sha'})
        mock_YumMetadataGenerator.assert_called_with(ANY, checksum_type='sha1',
                                                     skip_metadata_types=ANY, is_cancelled=ANY,
                                                     group_xml_path=ANY,
                                                     updateinfo_xml_path=ANY,
                                                     custom_metadata_dict=ANY)
        self.assertFalse(mock_distributor_manager.return_value.update_distributor_config.called)

    @patch('pulp.server.managers.factory.repo_distributor_manager')
    @patch('pulp_rpm.yum_plugin.metadata.YumMetadataGenerator')
    def test_yum_plugin_generate_yum_metadata_checksum_default(self, mock_YumMetadataGenerator,
                                                               mock_distributor_manager):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_publish"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_c/"
        existing_units = self.get_units(count=num_units)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm",
                                                                existing_units=existing_units,
                                                                checksum_type=None,
                                                                pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir,
                                                    relative_url=relative_url,
                                                    http=False, https=True)
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        config_conduit = mock.Mock(spec=RepoConfigConduit)
        config_conduit.get_repo_distributors_by_relative_url.return_value = MockCursor([])
        metadata.generate_yum_metadata(repo.id, repo.working_dir, publish_conduit, config)
        mock_YumMetadataGenerator.assert_called_with(ANY, checksum_type=metadata.DEFAULT_CHECKSUM,
                                                     skip_metadata_types=ANY, is_cancelled=ANY,
                                                     group_xml_path=ANY,
                                                     updateinfo_xml_path=ANY,
                                                     custom_metadata_dict=ANY)
        self.assertFalse(mock_distributor_manager.called)

    def test_metadata_get_repo_checksum_type(self):
        publish_conduit = mock.MagicMock()
        config = mock.MagicMock()
        config.get.return_value = None

        self.assertEquals(metadata.DEFAULT_CHECKSUM,
                          metadata.get_repo_checksum_type(publish_conduit, config))


    def test_basic_repo_publish_rel_path_conflict(self):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_basic_repo_publish_rel_path_conflict"
        num_units = 10
        relative_url = "rel_a/rel_b/rel_a/"
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir,
                relative_url=relative_url, http=False, https=True)

        url_a = relative_url
        config_a = PluginCallConfiguration({"relative_url":url_a}, {})
        repo_a = RelatedRepository("repo_a_id", [config_a])

        config_conduit = mock.Mock(spec=RepoConfigConduit)
        conduit_return_cursor = MockCursor([{'repo_id': 'repo_a_id', 'config': {'relative_url': "rel_a/rel_b/rel_a/"}}])

        config_conduit.get_repo_distributors_by_relative_url.return_value = conduit_return_cursor

        # Simple check of direct conflict of a duplicate - varieties of duplicates are tested via the conduit tests
        related_repos = [repo_a]
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        status, msg = distributor.validate_config(repo, config, config_conduit)
        self.assertFalse(status)
        expected_msg = "Relative url '%s' conflicts with existing relative_url of '%s' from repo '%s'" % \
                       (relative_url, url_a, repo_a.id)
        self.assertEqual(expected_msg, msg)

        # Ensure this test can handle a large number of repos
        """
        test_repos = []
        for index in range(0,10000):
            test_url = "rel_a/rel_b/rel_e/repo_%s" % (index)
            test_config = PluginCallConfiguration({"relative_url":test_url}, {})
            r = RelatedRepository("repo_%s_id" % (index), [test_config])
            test_repos.append(r)
        related_repos = test_repos
        distributor = YumDistributor()
        distributor.process_repo_auth_certificate_bundle = mock.Mock()
        status, msg = distributor.validate_config(repo, config, self.config_conduit)
        self.assertTrue(status)
        self.assertEqual(msg, None)
        """

    @mock.patch('pulp.server.managers.factory.repo_distributor_manager')
    def test_publish_progress(self, mock_manager):
        global progress_status
        progress_status = None

        def set_progress(progress):
            global progress_status
            progress_status = progress
        PROGRESS_FIELDS = ["num_success", "num_error", "items_left", "items_total", "error_details"]
        publish_conduit = distributor_mocks.get_publish_conduit(pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, http_publish_dir=self.http_publish_dir,
                relative_url="rel_temp/",
            generate_metadata=True, http=True, https=False)
        distributor = YumDistributor()
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_progress_sync"
        publish_conduit.repo_id = repo.id
        publish_conduit.distributor_id = 'foo'
        publish_conduit.set_progress = mock.Mock()
        publish_conduit.set_progress.side_effect = set_progress
        distributor.publish_repo(repo, publish_conduit, config)

        self.assertTrue(progress_status is not None)
        self.assertTrue("packages" in progress_status)
        self.assertTrue(progress_status["packages"].has_key("state"))
        self.assertEqual(progress_status["packages"]["state"], "FINISHED")
        for field in PROGRESS_FIELDS:
            self.assertTrue(field in progress_status["packages"])

        self.assertTrue("distribution" in progress_status)
        self.assertTrue(progress_status["distribution"].has_key("state"))
        self.assertEqual(progress_status["distribution"]["state"], "FINISHED")
        for field in PROGRESS_FIELDS:
            self.assertTrue(field in progress_status["distribution"])

        self.assertTrue("metadata" in progress_status)
        self.assertTrue(progress_status["metadata"].has_key("state"))
        self.assertEqual(progress_status["metadata"]["state"], "FINISHED")

        self.assertTrue("publish_http" in progress_status)
        self.assertEqual(progress_status["publish_http"]["state"], "FINISHED")
        self.assertTrue("publish_https" in progress_status)
        self.assertEqual(progress_status["publish_https"]["state"], "SKIPPED")


    def test_remove_symlink(self):

        pub_dir = self.http_publish_dir
        link_path = os.path.join(pub_dir, "a", "b", "c", "d", "e")
        os.makedirs(link_path)
        link_path = os.path.join(link_path, "temp_link").rstrip('/')
        os.symlink(self.https_publish_dir, link_path)
        self.assertTrue(os.path.exists(link_path))

        util.remove_repo_publish_dir(pub_dir, link_path)
        self.assertFalse(os.path.exists(link_path))
        self.assertEqual(len(os.listdir(pub_dir)), 1)

    def test_consumer_payload(self):
        PAYLOAD_FIELDS = [ 'server_name', 'relative_path',
                          'protocols', 'gpg_keys', 'client_cert', 'ca_cert', 'repo_name']
        http = True
        https = True
        relative_url = "/pub/content/"
        gpgkey = ["test_gpg_key",]
        auth_cert = open(os.path.join(self.data_dir, "cert.crt")).read()
        auth_ca = open(os.path.join(self.data_dir, "ca.key")).read()
        config = distributor_mocks.get_basic_config(relative_url=relative_url, http=http, https=https, auth_cert=auth_cert, auth_ca=auth_ca, gpgkey=gpgkey)
        distributor = YumDistributor()
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_payload"
        repo.display_name = 'Nice Repo'
        payload = distributor.create_consumer_payload(repo, config, None)
        for field in PAYLOAD_FIELDS:
            self.assertTrue(field in payload)

        self.assertTrue('http' in payload['protocols'])
        self.assertTrue('https' in payload['protocols'])

    @mock.patch('pulp.server.managers.factory.repo_distributor_manager')
    @mock.patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_distributor_removed(self, delete_protected_repo, mock_factory):
        """
        Make sure the distributor_removed() method cleans up the published files.
        """
        # Create and publish repo to both http and https directories
        repo = mock.Mock(spec=Repository)
        repo.id = 'about_to_be_removed'
        repo.working_dir = self.repo_working_dir
        existing_units = self.get_units(count=5)
        publish_conduit = distributor_mocks.get_publish_conduit(type_id="rpm",
                                                                existing_units=existing_units,
                                                                pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(http_publish_dir=self.http_publish_dir,
                                                    https_publish_dir=self.https_publish_dir,
                                                    http=True,
                                                    https=True)
        distributor = YumDistributor()
        publish_conduit.repo_id = repo.id
        publish_conduit.distributor_id = 'foo'
        report = distributor.publish_repo(repo, publish_conduit, config)

        publishing_paths = [os.path.join(directory, repo.id) \
                            for directory in [self.http_publish_dir, self.https_publish_dir]]
        # The publishing paths should exist
        self.assertTrue(all([os.path.exists(directory) for directory in publishing_paths]))
        delete_protected_repo.reset_mock()
        distributor.distributor_removed(repo, config)
        # Neither publishing path should exist now
        self.assertFalse(all([os.path.exists(directory) for directory in publishing_paths]))
        # delete_protected_repo should have been called
        delete_protected_repo.assert_called_once_with(repo.id)
