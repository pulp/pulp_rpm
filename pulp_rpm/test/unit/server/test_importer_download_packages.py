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

from pulp_rpm.plugins.importers.download.packages import Packages

from http_test_server import HTTPStaticTestServer, relative_path_to_data_dir


TEST_URL = 'http://localhost:8088/'
TEST_DIR = '/tmp/pulp_rpm/packages/'
TEST_REPO_PATH = '../data/test_repo/'


class PackagesInstantiationTests(unittest.TestCase):

    def test_instantiation(self):
        try:
            Packages(TEST_URL + TEST_REPO_PATH, [], TEST_DIR)
        except Exception, e:
            self.fail(str(e))


class RequestGeneratorTests(unittest.TestCase):

    def test_request_generator(self):
        package_info_list = []
        packages = Packages(TEST_URL + TEST_REPO_PATH, package_info_list, TEST_DIR)
        request_generator = packages._request_generator()


class LiveDownloadsTests(unittest.TestCase):

    server = None
    repo_url = TEST_URL + relative_path_to_data_dir('../data/test_repo/')

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPStaticTestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.server = None

    def setUp(self):
        if not os.path.exists(TEST_DIR):
            os.makedirs(TEST_DIR)

    def tearDown(self):
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)

