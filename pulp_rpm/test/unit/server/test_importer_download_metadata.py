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
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
import shutil
import unittest

from pulp_rpm.plugins.importers.download import metadata

from http_test_server import HTTPStaticTestServer, relative_path_to_data_dir

# global test data -------------------------------------------------------------

TEST_URL = 'http://localhost:8088/'
TEST_DIR = '/tmp/pulp_rpm/metadata_tests/'
TEST_REPO_PATH = '../data/test_repo/'

# metadata tests base class for live downloads ---------------------------------

class MetadataTests(unittest.TestCase):

    http_server = None

    @classmethod
    def setUpClass(cls):
        cls.http_server = HTTPStaticTestServer()
        cls.http_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.http_server.stop()
        cls.http_server = None

    def setUp(self):
        if not os.path.exists(TEST_DIR):
            os.makedirs(TEST_DIR)

    def tearDown(self):
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)

# metadata tests ---------------------------------------------------------------

class MetadataFilesInstantiationTests(unittest.TestCase):

    def test_metadata_files_instance(self):
        try:
            metadata.MetadataFiles(TEST_URL, TEST_DIR)
        except Exception, e:
            self.fail(str(e))


class RepomdParsingTests(unittest.TestCase):

    def test_test_repo(self):
        # this relies on the pulp_rpm/test/unit/data/test_repo/ repository
        repodata_path = TEST_REPO_PATH + 'repodata'
        metadata_files = metadata.MetadataFiles(TEST_URL, repodata_path) # url param unused
        metadata_files.parse_repomd()

        # check the revision was set correctly
        self.assertEqual(metadata_files.revision, '1283359366')

        # check that the metadata types are there
        self.assertTrue('product' in metadata_files.metadata)
        self.assertTrue('group' in metadata_files.metadata)
        self.assertTrue('filelists' in metadata_files.metadata)
        self.assertTrue('updateinfo' in metadata_files.metadata)
        self.assertTrue('group_gz' in metadata_files.metadata)
        self.assertTrue('primary' in metadata_files.metadata)
        self.assertTrue('other' in metadata_files.metadata)

        # select a metadata type and test it
        self.assertEqual(metadata_files.metadata['product']['checksum']['algorithm'], 'sha256')
        self.assertEqual(metadata_files.metadata['product']['checksum']['hex_digest'], '854c463fd8138340b1ba2fbecd3abb18d44a13a7c35753640880471bf4aea20a')
        self.assertEqual(metadata_files.metadata['product']['size'], 1547)
        self.assertEqual(metadata_files.metadata['product']['relative_path'], 'repodata/854c463fd8138340b1ba2fbecd3abb18d44a13a7c35753640880471bf4aea20a-product.gz')


class LiveDownloadTests(MetadataTests):

    # this relies on the pulp_rpm/test/unit/data/test_repo/ repository
    repo_url = TEST_URL + relative_path_to_data_dir(TEST_REPO_PATH)

    def _test_repomd_download(self):
        metadata_files = metadata.MetadataFiles(self.repo_url, TEST_DIR)
        metadata_files.download_repomd()

        self.assertTrue(os.path.exists(os.path.join(TEST_DIR, 'repomd.xml')))
        self.fail(self.repo_url)

