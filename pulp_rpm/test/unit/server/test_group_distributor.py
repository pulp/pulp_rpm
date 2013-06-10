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

from uuid import uuid4
import mock
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/distributors/")

from pulp.plugins.model import Repository, Unit, RepositoryGroup

from iso_distributor import iso_util
from iso_distributor.exporter import RepoExporter
from iso_distributor.generate_iso import GenerateIsos
from iso_distributor.groupdistributor import (GroupISODistributor, TYPE_ID_DISTRIBUTOR_EXPORT,
                                              TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                              TYPE_ID_DISTRO, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP)
from pulp_rpm.repo_auth.repo_cert_utils import M2CRYPTO_HAS_CRL_SUPPORT
from rpm_support_base import PULP_UNITTEST_REPO_URL, PulpRPMTests
import group_distributor_mocks as distributor_mocks
import importer_mocks


class TestGroupISODistributor(PulpRPMTests):

    def setUp(self):
        super(TestGroupISODistributor, self).setUp()
        self.init()

    def tearDown(self):
        super(TestGroupISODistributor, self).tearDown()
        self.clean()

    def init(self):
        self.temp_dir = tempfile.mkdtemp()
        #pkg_dir is where we simulate units actually residing
        self.pkg_dir = os.path.join(self.temp_dir, "packages")
        os.makedirs(self.pkg_dir)
        #distro_dir is where we simulate units actually residing
        self.distro_dir = os.path.join(self.temp_dir, "distribution")
        os.makedirs(self.distro_dir)
        #publish_dir simulates /var/lib/pulp/published
        self.http_publish_dir = os.path.join(self.temp_dir, "publish", "http", "isos")
        os.makedirs(self.http_publish_dir)

        self.https_publish_dir = os.path.join(self.temp_dir, "publish", "https", "isos")
        os.makedirs(self.https_publish_dir)

        self.repo_working_dir = os.path.join(self.temp_dir, "repo_working_dir")
        os.makedirs(self.repo_working_dir)

        self.group_working_dir = os.path.join(self.temp_dir, "group_working_dir")
        os.makedirs(self.group_working_dir)

        self.repo_iso_working_dir = os.path.join(self.temp_dir, "repo_working_dir", "isos")
        os.makedirs(self.repo_iso_working_dir)

        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data"))

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def test_metadata(self):
        metadata = GroupISODistributor.metadata()
        self.assertEquals(metadata["id"], TYPE_ID_DISTRIBUTOR_EXPORT)
        for type in [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO,
                     TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]:
            self.assertTrue(type in metadata["types"])

    def test_validate_config(self):
        distributor = GroupISODistributor()
        repo = mock.Mock(spec=Repository)
        repo.id = "testrepo"
        http = "true"
        https = False
        config = distributor_mocks.get_basic_config(http=http, https=https)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        http = True
        config = distributor_mocks.get_basic_config(http=http, https=https)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

        http = True
        https = "False"
        relative_url = "test_path"
        config = distributor_mocks.get_basic_config(http=http, https=https)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        https = True
        config = distributor_mocks.get_basic_config(http=http, https=https)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

        http = True
        https = False
        relative_url = "test_path"
        skip_content_types = "fake"
        config = distributor_mocks.get_basic_config(http=http, https=https,
            skip=skip_content_types)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        skip_content_types = []
        config = distributor_mocks.get_basic_config(http=http, https=https,
            skip=skip_content_types)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

        # test invalid iso prefix
        config = distributor_mocks.get_basic_config(http=True, https=False, iso_prefix="my_iso*_name_/")
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)
        # test valid iso prefix
        config = distributor_mocks.get_basic_config(http=True, https=False, iso_prefix="My_iso_name-01")
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

        invalid_config="dummy"
        config = distributor_mocks.get_basic_config(invalid_config)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        http_publish_dir = self.http_publish_dir
        config = distributor_mocks.get_basic_config(http=http, https=https,
            http_publish_dir=http_publish_dir)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

        http_publish_dir = "test"
        config = distributor_mocks.get_basic_config(http=http, https=https,
            http_publish_dir=http_publish_dir)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        https_publish_dir = self.https_publish_dir
        config = distributor_mocks.get_basic_config(http=http, https=https,
            https_publish_dir=https_publish_dir)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

        https_publish_dir = "test"
        config = distributor_mocks.get_basic_config(http=http, https=https,
            https_publish_dir=https_publish_dir)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        if not M2CRYPTO_HAS_CRL_SUPPORT:
            return
        http = True
        https = False
        relative_url = "test_path"
        auth_cert = "fake"
        config = distributor_mocks.get_basic_config(http=http, https=https,
            https_ca=auth_cert)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertFalse(state)

        auth_cert = open(os.path.join(self.data_dir, "cert.crt")).read()
        config = distributor_mocks.get_basic_config(http=http, https=https,
            https_ca=auth_cert)
        state, msg = distributor.validate_config(repo, config, [])
        self.assertTrue(state)

    def test_publish_progress(self):
        global progress_status
        progress_status = None
        group_progress_status = None
        def set_progress(progress):
            global progress_status
            progress_status = progress
        PROGRESS_FIELDS = ["num_success", "num_error", "items_left", "items_total", "error_details"]
        publish_conduit = distributor_mocks.get_publish_conduit(pkg_dir=self.pkg_dir)
        config = distributor_mocks.get_basic_config(https_publish_dir=self.https_publish_dir, http_publish_dir=self.http_publish_dir,
            generate_metadata=True, http=True, https=False)
        distributor = GroupISODistributor()
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.repo_working_dir
        repo.id = "test_progress_sync"
        repo_group = mock.Mock(spec=RepositoryGroup)
        repo_group.id = "test_group"
        repo_group.repo_ids = [repo.id,]
        repo_group.working_dir = self.group_working_dir
        publish_conduit.set_progress = mock.Mock()
        publish_conduit.set_progress.side_effect = set_progress
        distributor.publish_group(repo_group, publish_conduit, config)
        self.assertTrue(progress_status is not None)
        self.assertEqual(progress_status['group-id'], repo_group.id)
        self.assertTrue("rpms" in progress_status['repositories'][repo.id])
        self.assertTrue(progress_status['repositories'][repo.id]["rpms"].has_key("state"))
        self.assertEqual(progress_status['repositories'][repo.id]["rpms"]["state"], "FINISHED")
        for field in PROGRESS_FIELDS:
            self.assertTrue(field in progress_status['repositories'][repo.id]["rpms"])

        self.assertTrue("distribution" in progress_status['repositories'][repo.id])
        self.assertTrue(progress_status['repositories'][repo.id]["distribution"].has_key("state"))
        self.assertEqual(progress_status['repositories'][repo.id]["distribution"]["state"], "FINISHED")
        for field in PROGRESS_FIELDS:
            self.assertTrue(field in progress_status['repositories'][repo.id]["distribution"])

        self.assertTrue("errata" in progress_status['repositories'][repo.id])
        self.assertTrue(progress_status['repositories'][repo.id]["errata"].has_key("state"))
        self.assertEqual(progress_status['repositories'][repo.id]["errata"]["state"], "FINISHED")

        self.assertTrue("isos" in progress_status)
        self.assertTrue(progress_status["isos"].has_key("state"))
        self.assertEqual(progress_status["isos"]["state"], "FINISHED")
        ISO_PROGRESS_FIELDS = ["num_success", "num_error", "items_left", "items_total", "error_details", "written_files", "current_file", "size_total", "size_left"]
        for field in ISO_PROGRESS_FIELDS:
            self.assertTrue( field in progress_status["isos"])

        self.assertTrue("publish_http" in progress_status)
        self.assertEqual(progress_status["publish_http"]["state"], "FINISHED")
        self.assertTrue("publish_https" in progress_status)
        self.assertEqual(progress_status["publish_https"]["state"], "SKIPPED")
