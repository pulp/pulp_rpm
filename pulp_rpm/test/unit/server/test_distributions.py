# -*- coding: utf-8 -*-
#
# Copyright © 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from urlparse import urljoin
import glob
import mock
import os
import shutil
import sys
import tempfile

from pulp.plugins.model import Repository, Unit

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")

from pulp_rpm.common.ids import TYPE_ID_DISTRO, TYPE_ID_IMPORTER_YUM
from rpm_support_base import PULP_UNITTEST_REPO_URL, PulpRPMTests, ZOO_REPO_URL
from yum_importer import importer_rpm, distribution
from yum_importer.importer import YumImporter
import importer_mocks

class TestDistribution(PulpRPMTests):

    def setUp(self):
        super(TestDistribution, self).setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.working_dir = os.path.join(self.temp_dir, "working")
        self.pkg_dir = os.path.join(self.temp_dir, "packages")
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), "data"))

    def tearDown(self):
        super(TestDistribution, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_metadata(self):
        metadata = YumImporter.metadata()
        self.assertEquals(metadata["id"], TYPE_ID_IMPORTER_YUM)
        self.assertTrue(TYPE_ID_DISTRO in metadata["types"])

    def test_distributions_sync(self):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.working_dir
        repo.id = "test_repo"
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=self.pkg_dir)
        config = importer_mocks.get_basic_config(feed_url=PULP_UNITTEST_REPO_URL)
        importerRPM = importer_rpm.ImporterRPM()
        status, summary, details = importerRPM.sync(repo, sync_conduit, config)
        self.assertTrue(status)
        self.assertTrue(summary is not None)
        self.assertTrue(details is not None)
        self.assertEquals(summary["num_synced_new_distributions"], 1)
        self.assertEquals(summary["num_synced_new_distributions_files"], 3)
        self.assertEquals(summary["num_resynced_distributions"], 0)
        self.assertEquals(summary["num_resynced_distribution_files"], 0)

        distro_tree_files = glob.glob("%s/%s/images/*" % (repo.working_dir, repo.id))
        self.assertEquals(len(distro_tree_files), 3)

    def test_orphaned_distributions(self):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.working_dir
        repo.id = "test_repo"
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=self.pkg_dir)
        config = importer_mocks.get_basic_config(feed_url=PULP_UNITTEST_REPO_URL)
        importerRPM = importer_rpm.ImporterRPM()
        status, summary, details = importerRPM.sync(repo, sync_conduit, config)
        self.assertTrue(status)
        dunit_key = {}
        dunit_key['id'] = "ks-TestFamily-TestVariant-16-x86_64"
        dunit_key['version'] = "16"
        dunit_key['arch'] = "x86_64"
        dunit_key['family'] = "TestFamily"
        dunit_key['variant'] = "TestVariant"
        metadata = {
            "files" : [
                {"checksumtype": "sha256", "relativepath": "images/fileA.txt",
                 "fileName": "fileA.txt",
                 "downloadurl": urljoin(PULP_UNITTEST_REPO_URL, '/images/fileA.txt'),
                 "item_type": "tree_file",
                 "savepath": "%s/testr1/images" % self.working_dir,
                 "checksum": "22603a94360ee24b7034c74fa13d70dd122aa8c4be2010fc1361e" +\
                              '1e6b0b410ab',
                 "filename": "fileA.txt",
                 "pkgpath": "%s/ks-TestFamily-TestVariant-16-x86_64/images" %\
                            self.pkg_dir,
                 "size": 0},
                {"checksumtype": "sha256", 	"relativepath": "images/fileB.txt",
                 "fileName": "fileB.txt",
                 "downloadurl": urljoin(PULP_UNITTEST_REPO_URL, "/images/fileB.txt"),
                 "item_type": "tree_file",
                 "savepath": "%s/testr1/images" % self.working_dir,
                 "checksum": "8dc89e9883c098443f6616e60a8e489254bf239eeade6e4b4943b" +\
                              "7c8c0c345a4",
                 "filename": "fileB.txt",
                 "pkgpath": "%s/ks-TestFamily-TestVariant-16-x86_64/images" %\
                            self.pkg_dir,
                 "size": 0 },
                {"checksumtype": "sha256", 	"relativepath": "images/fileC.iso",
                 "fileName": "fileC.iso",
                 "downloadurl": urljoin(PULP_UNITTEST_REPO_URL, "/images/fileC.iso"),
                 "item_type": "tree_file",
                 "savepath": "%s/testr1/images" % self.working_dir,
                 "checksum": "099f2bafd533e97dcfee778bc24138c40f114323785ac1987a0db" +\
                              "66e07086f74",
                 "filename": "fileC.iso",
                 "pkgpath": "%s/ks-TestFamily-TestVariant-16-x86_64/images" %\
                            self.pkg_dir,
                 "size": 0 }]}
        distro_unit = Unit(distribution.TYPE_ID_DISTRO, dunit_key, metadata, '')
        distro_unit.storage_path = "%s/ks-TestFamily-TestVariant-16-x86_64" %\
                                   self.pkg_dir
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=self.pkg_dir,
                                                       existing_units=[distro_unit])
        config = importer_mocks.get_basic_config(feed_url=ZOO_REPO_URL)
        status, summary, details = importerRPM.sync(repo, sync_conduit, config)
        self.assertTrue(status)
        self.assertTrue(summary is not None)
        self.assertTrue(details is not None)
        self.assertEquals(summary["num_orphaned_distributions"], 1)
